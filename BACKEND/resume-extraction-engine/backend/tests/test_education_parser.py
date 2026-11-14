from app.parser.common import lines_from_text
from app.parser.education_parser import find_degree, parse_education


def test_degree_field():
    assert find_degree("Bachelor of Technology in Computer Science and Engineering, IIT")[:2] == (
        "Bachelor of Technology", "Computer Science and Engineering")
    assert find_degree("B.Tech (CSE)")[:2] == ("B.Tech", "CSE")
    assert find_degree("they will be there") is None                    # 'be' is not a degree


def test_multiple_entries_and_grades():
    ls = lines_from_text(
        "Delhi University\nM.Sc. in Data Science 2021 - 2023 CGPA: 3.8/4\n"
        "St. Xavier's College, Mumbai\nBSc Physics | 2018 - 2021 | First Class\nPercentage: 78.5%")
    e = parse_education(ls)
    assert len(e) == 2
    assert (e[0].degree, e[0].cgpa, e[0].cgpa_scale, e[0].graduation_year) == ("M.Sc", 3.8, 4.0, 2023)
    assert e[1].institution.startswith("St. Xavier") and e[1].grade == "First Class" and e[1].percentage == 78.5


def test_expected_graduation_and_ongoing():
    e = parse_education(lines_from_text("MIT Institute of Technology\nB.E. Computer Science, Expected May 2026"))
    assert e[0].end_date == "2026-05"
    e = parse_education(lines_from_text("Amity University\nMBA | 2024 - Present"))
    assert e[0].is_current and e[0].graduation_year is None


def test_no_invention_on_garbage():
    assert parse_education(lines_from_text("lorem ipsum dolor sit amet")) == []
