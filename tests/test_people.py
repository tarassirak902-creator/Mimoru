from app.services.people import calculate_reputation, trust_label

def test_good_member_reputation():
    r=calculate_reputation(messages=2000,warnings=0,mutes=0,bans=0,complaints=0,days_in_group=365)
    assert r.score >= 80 and r.trust == "trusted"

def test_problem_member_reputation():
    r=calculate_reputation(messages=20,warnings=3,mutes=2,bans=1,complaints=5,days_in_group=10)
    assert r.score < 35 and r.trust == "watch"

def test_override_is_clamped():
    assert calculate_reputation(messages=0,warnings=0,mutes=0,bans=0,complaints=0,days_in_group=0,override=150).score == 100

def test_trust_label():
    assert "Проверенный" in trust_label("trusted")
