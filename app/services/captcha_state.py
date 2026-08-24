from __future__ import annotations

from redis.asyncio import Redis


PENDING_BAN = "pending_ban"
BAN_INFLIGHT = "ban_inflight"
PENDING_UNBAN = "pending_unban"
VERIFIED = "verified"
PROCESSING_TTL_SECONDS = 3600


CAPTCHA_EXPIRY_CLAIM_LUA = r"""
local current = redis.call('GET', KEYS[1])
if not current then
    return 0
end
if current ~= ARGV[1] then
    return 0
end
local deadline = tonumber(current)
if not deadline then
    return -2
end
local now = tonumber(ARGV[2])
if deadline > now then
    return 0
end
redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[4])
return 1
"""


CAPTCHA_VERIFY_CLAIM_LUA = r"""
local current = redis.call('GET', KEYS[1])
if not current then
    return 0
end
if current == ARGV[2] then
    return 2
end
local deadline = tonumber(current)
if not deadline then
    return 0
end
local now = tonumber(ARGV[1])
if deadline <= now then
    return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""


CAPTCHA_DELETE_STATE_LUA = r"""
local current = redis.call('GET', KEYS[1])
if current ~= ARGV[1] then
    return 0
end
return redis.call('DEL', KEYS[1])
"""


CAPTCHA_REFRESH_STATE_LUA = r"""
local current = redis.call('GET', KEYS[1])
if current ~= ARGV[1] then
    return 0
end
return redis.call('EXPIRE', KEYS[1], ARGV[2])
"""


async def claim_expired_captcha(
    redis: Redis,
    key: str,
    raw_deadline: str,
    now_ts: int,
) -> int:
    return int(await redis.eval(
        CAPTCHA_EXPIRY_CLAIM_LUA,
        1,
        key,
        raw_deadline,
        str(now_ts),
        PENDING_BAN,
        str(PROCESSING_TTL_SECONDS),
    ))


async def claim_verified_captcha(redis: Redis, key: str, now_ts: int) -> int:
    return int(await redis.eval(
        CAPTCHA_VERIFY_CLAIM_LUA,
        1,
        key,
        str(now_ts),
        VERIFIED,
        str(PROCESSING_TTL_SECONDS),
    ))


async def delete_captcha_state(redis: Redis, key: str, expected_state: str) -> bool:
    return bool(await redis.eval(
        CAPTCHA_DELETE_STATE_LUA,
        1,
        key,
        expected_state,
    ))


async def refresh_captcha_state_ttl(redis: Redis, key: str, expected_state: str) -> bool:
    """Extend only the still-current recovery state; never resurrect a replaced winner."""
    return bool(await redis.eval(
        CAPTCHA_REFRESH_STATE_LUA,
        1,
        key,
        expected_state,
        str(PROCESSING_TTL_SECONDS),
    ))
