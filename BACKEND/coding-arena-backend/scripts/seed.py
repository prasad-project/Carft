"""Dev seed: all spec domains + 45 generated 'predict the output' Python questions (answers computed by eval)."""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database.models import Domain, Question  # noqa: E402
from app.database.session import SessionLocal, create_all  # noqa: E402
from app.services.question_service import text_hash  # noqa: E402

TREE = {
    "Programming Languages": ["Python", "Java", "C", "C++", "JavaScript", "TypeScript", "PHP", "Go", "Rust", "Kotlin",
                              "Swift", "C#"],
    "Database": ["SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis"],
    "Data and AI": ["Machine Learning", "Deep Learning", "Artificial Intelligence", "Generative AI", "Agentic AI",
                    "Natural Language Processing", "Data Science", "Data Analytics", "Data Engineering", "Big Data"],
    "Software Engineering": ["Backend Development", "Frontend Development", "Full Stack Development",
                             "Software Engineering", "System Design", "API Development", "Microservices",
                             "Software Architecture"],
    "Cloud and DevOps": ["AWS", "Azure", "Google Cloud", "Docker", "Kubernetes", "CI/CD", "DevOps", "Cloud Computing"],
    "Computer Science": ["Data Structures and Algorithms", "Operating Systems", "Computer Networks",
                         "Computer Architecture", "Object-Oriented Programming", "Software Testing", "Cybersecurity"],
}


def slug(n: str) -> str:
    return n.lower().replace("+", "p").replace("#", "sharp").replace("/", "-").replace(" ", "-")


def gen_questions(n: int = 45):
    rng = random.Random(7)
    out, seen = [], set()
    while len(out) < n:
        k = rng.choice(["len", "sum", "max", "pow", "floor", "mod", "slice", "rev"])
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        lst = rng.sample(range(1, 20), rng.randint(3, 5))
        code = {"len": f"print(len({lst}))", "sum": f"print(sum(range({a})))", "max": f"print(max({lst}))",
                "pow": f"print({a} ** {b})", "floor": f"print({a * b + 1} // {b})", "mod": f"print({a * b + a} % {b})",
                "slice": f"print('python'[{a % 3}:{a % 3 + b % 3 + 1}])", "rev": f"print({lst}[::-1][0])"}[k]
        if code in seen:
            continue
        seen.add(code)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(code)  # trusted, generated above
        right = buf.getvalue().strip()
        wrong = []
        while len(wrong) < 3:
            w = str(int(right) + rng.choice([-3, -2, -1, 1, 2, 4])) if right.lstrip("-").isdigit() else rng.choice(
                ["pyt", "tho", "yth", "hon", "pytho"])
            if w != right and w not in wrong:
                wrong.append(w)
        opts = [right] + wrong
        rng.shuffle(opts)
        out.append({"text": "What is the output of the code?", "code": code, "opts": opts, "right": right,
                    "diff": rng.choice(["EASY", "MEDIUM", "HARD"])})
    return out


async def main():
    await create_all()
    async with SessionLocal() as s:
        by_slug = {d.slug: d for d in (await s.execute(select(Domain))).scalars()}
        for parent, kids in TREE.items():
            p = by_slug.get(slug(parent)) or Domain(name=parent, slug=slug(parent), description=f"{parent} category")
            if p.id is None or slug(parent) not in by_slug:
                s.add(p)
                await s.flush()
                by_slug[p.slug] = p
            for k in kids:
                if slug(k) not in by_slug:
                    d = Domain(name=k, slug=slug(k), parent_id=p.id, description=f"{k} MCQs")
                    s.add(d)
                    by_slug[d.slug] = d
        await s.flush()
        py = by_slug["python"]
        added = 0
        for g in gen_questions():
            h = text_hash(g["text"], g["code"])
            if (await s.execute(select(Question.id).where(Question.text_hash == h))).first():
                continue
            s.add(Question(domain_id=py.id, question_text=g["text"], code_snippet=g["code"], question_type="PREDICT_OUTPUT",
                           options=[{"id": L, "text": t} for L, t in zip("ABCD", g["opts"])],
                           correct_option="ABCD"[g["opts"].index(g["right"])], difficulty=g["diff"], status="PUBLISHED",
                           explanation=f"Running `{g['code']}` prints {g['right']}.", topic="basics", source="generated",
                           text_hash=h))
            added += 1
        await s.commit()
        print(f"domains: {len(by_slug)}, python questions added: {added}")


if __name__ == "__main__":
    asyncio.run(main())
