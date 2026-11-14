from app.parser.common import lines_from_text
from app.parser.project_parser import parse_projects


def test_multiple_projects_with_urls_and_tech():
    ls = lines_from_text(
        "Chat App (React, Node.js, MongoDB) github.com/u/chat 2023\n"
        "Real-time messaging with websockets.\n• Handled 5k concurrent users\n• Added JWT auth\n"
        "Stock Predictor | Python, TensorFlow\nTech Stack: Pandas, Flask\n• Reached 87% accuracy")
    p = parse_projects(ls)
    assert [x.name for x in p] == ["Chat App", "Stock Predictor"]
    assert p[0].github_url == "https://github.com/u/chat" and p[0].start_date == "2023"
    assert {"React", "Node.js", "MongoDB"} <= set(p[0].technologies)
    assert p[0].description.startswith("Real-time") and len(p[0].bullet_points) == 2
    assert {"Python", "TensorFlow", "Pandas", "Flask"} <= set(p[1].technologies)
    assert p[1].achievements == ["Reached 87% accuracy"]
