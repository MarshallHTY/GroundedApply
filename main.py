from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.criteria_tools import build_application_pack, application_pack_to_markdown


def read_text(path: str | None, fallback: str = "") -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(description="GroundedApply CLI")
    parser.add_argument("--job", default="examples/sample_job_advert.txt", help="Path to job advert / criteria text")
    parser.add_argument("--experience", default="examples/sample_experience_bank.txt", help="Path to experience bank text")
    parser.add_argument("--target-role", default="Data Analyst / Data Scientist")
    parser.add_argument("--tone", choices=["professional", "concise"], default="professional")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--out", default="outputs/application_pack.md")
    args = parser.parse_args()

    job_advert = read_text(args.job)
    experience_bank = read_text(args.experience)
    pack = build_application_pack(job_advert, experience_bank, args.target_role, args.tone)

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        output_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        output_path.write_text(application_pack_to_markdown(pack), encoding="utf-8")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
