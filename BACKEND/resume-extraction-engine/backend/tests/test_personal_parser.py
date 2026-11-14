from app.parser.common import lines_from_text
from app.parser.contact_parser import find_email, find_location, find_phone
from app.parser.personal_parser import find_headline, find_name
from app.parser.url_parser import classify_url, extract_urls


def L(t):
    return lines_from_text(t)


def test_name_not_always_first_line():
    ls = L("Curriculum Vitae\nRahul K. Verma\nData Scientist\nrahul.verma@mail.com")
    assert find_name(ls, "rahul.verma@mail.com")[0] == "Rahul K. Verma"


def test_all_caps_name_titlecased_and_email_boosts_confidence():
    n = find_name(L("JOHN DOE\nSoftware Engineer"), "john.doe@x.com")
    assert n[0] == "John Doe" and n[4] >= 0.85


def test_job_title_and_city_are_not_names():
    assert find_name(L("Software Engineer\nNew Delhi"), None) is None


def test_phone_formats():
    assert find_phone(L("+91-98765-43210"))[0].startswith("+91")
    assert find_phone(L("(415) 555-0132"))[0] == "(415) 555-0132"
    assert find_phone(L("+44 20 7946 0958"))[0] == "+44 20 7946 0958"
    assert find_phone(L("B.Tech 2019 - 2023 | CGPA 8.9")) is None      # dates are not phones


def test_email_and_location():
    assert find_email(L("Mail: A.B@Corp.co.in | x"))[0] == "a.b@corp.co.in"
    assert find_location(L("Noida, Uttar Pradesh"))[0] == "Noida, Uttar Pradesh"
    assert find_location(L("Software Engineer | Python")) is None


def test_headline():
    ls = L("Jane Roe\nFull Stack Developer\njane@x.com")
    assert find_headline(ls, ls[0], "Jane Roe")[0] == "Full Stack Developer"


def test_urls():
    u = extract_urls("jane@gmail.com | linkedin.com/in/jane | https://github.com/jane/repo.")
    assert [classify_url(x) for x in u] == ["linkedin", "github_repo"]       # gmail.com is not a URL
