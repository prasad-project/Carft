from app.parser.common import lines_from_text
from app.parser.skills_parser import find_skills, inferred_from_context, parse_skills


def test_categorised_and_label_fallback():
    s = parse_skills(lines_from_text("Languages: Python, C++, R\nFrameworks: Django, MyCustomFW\nPostgreSQL | Redis\nSoft skills: Leadership"))
    assert s.programming_languages == ["Python", "C++", "R"]
    assert "MyCustomFW" in s.frameworks and "Django" in s.frameworks
    assert s.databases == ["PostgreSQL", "Redis"] and s.soft_skills == ["Leadership"]


def test_parenthesised_items_and_aliases():
    s = parse_skills(lines_from_text("Python (Pandas, NumPy), sklearn, powerbi"))
    assert {"Pandas", "NumPy"} <= set(s.libraries) and "Scikit-learn" in s.ai_ml and "Power BI" in s.data_analytics


def test_context_matching_is_strict():
    names = [n for n, _ in find_skills("Built Go services; we excel in teamwork; Spring was great; used 2M requests; React and Node.js")]
    assert names == ["React", "Node.js"]


def test_inferred_not_confirmed():
    conf = parse_skills(lines_from_text("Python"))
    inf = inferred_from_context(lines_from_text("Deployed with Docker and Python"), conf)
    assert inf == ["Docker"] and "Docker" not in conf.developer_tools


def test_sentences_not_skills():
    s = parse_skills(lines_from_text("I am a hardworking person who loves learning new things quickly"))
    assert sum(len(v) for v in s.model_dump().values()) == 0
