from pathlib import Path


def test_no_implementation_placeholders_in_application_code():
    root = Path('app')
    forbidden = ('NotImplementedError', 'TODO: implement', 'FIXME: implement')
    hits = []
    for path in root.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for marker in forbidden:
            if marker in text:
                hits.append(f'{path}:{marker}')
    assert not hits, hits
