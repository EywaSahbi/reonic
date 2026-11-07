"""Reproduce engine validation scores while keeping generated files inside qa/."""
from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
DATA = ROOT / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("val", "test", "both"), default="both")
    args = parser.parse_args()
    splits = ("val", "test") if args.split == "both" else (args.split,)

    sys.path.insert(0, str(ENGINE))
    import predict

    fitted_on = predict.PARAMS.get("derived_from_dataset", {}).get("split")
    if fitted_on != "train":
        raise AssertionError(f"engine params were fitted on {fitted_on!r}, expected train")

    spec = importlib.util.spec_from_file_location("qa_data_score", DATA / "score.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the official data scorer")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)

    with tempfile.TemporaryDirectory(prefix="score-", dir=Path(__file__).parent) as temp_dir:
        output_dir = Path(temp_dir)
        predict.OUT = output_dir
        original_write_text = Path.write_text
        reports_dir = (DATA / "reports").resolve()

        def write_to_qa(path: Path, content: str, *positional, **keywords):
            if path.resolve().parent == reports_dir:
                path = output_dir / path.name
            return original_write_text(path, content, *positional, **keywords)

        Path.write_text = write_to_qa
        try:
            for split in splits:
                sys.argv = [str(ENGINE / "predict.py"), "--split", split]
                predict.main()
                report = scorer.run(output_dir / f"predictions_{split}.csv", split)
                scorer.show(report)
                expected_n = {"val": 238, "test": 235}[split]
                if report["n"] != expected_n or report["missing_predictions"]:
                    raise AssertionError(
                        f"{split}: expected {expected_n} complete predictions, got "
                        f"n={report['n']}, missing={report['missing_predictions']}"
                    )
        finally:
            Path.write_text = original_write_text
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
