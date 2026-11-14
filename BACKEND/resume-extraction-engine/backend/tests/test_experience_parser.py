from app.parser.common import lines_from_text
from app.parser.date_parser import find_date_range
from app.parser.experience_parser import parse_experience


def test_date_formats():
    cases = {"Jan 2020 – Present": ("2020-01", None, True), "01/2019 - 03/2021": ("2019-01", "2021-03", False),
             "2018-2020": ("2018", "2020", False), "June - August 2021": ("2021-06", "2021-08", False),
             "Sept 2019 to Dec 2019": ("2019-09", "2019-12", False), "2017 – 19": ("2017", "2019", False)}
    for text, (s, e, cur) in cases.items():
        d = find_date_range(text)
        assert (d.start, d.end, d.is_current) == (s, e, cur), text


def test_two_line_header_and_bullets_with_wrap():
    ls = lines_from_text(
        "Senior Developer\nInfosys Limited, Pune\nMar 2019 – Dec 2022\n"
        "• Led migration of billing to microservices\nserving 2 million users\n"
        "• Wrote documentation\n"
        "Junior Developer | TCS | 2017 - 2019\n• Fixed bugs")
    e = parse_experience(ls)
    assert len(e) == 2
    assert (e[0].job_title, e[0].company, e[0].start_date) == ("Senior Developer", "Infosys Limited", "2019-03")
    assert e[0].location == "Pune"
    assert "Led migration of billing to microservices serving 2 million users" in e[0].achievements
    assert e[1].company == "TCS" and e[1].end_date == "2019"


def test_empty_when_no_signal():
    assert parse_experience(lines_from_text("hello there my friend")) == []
