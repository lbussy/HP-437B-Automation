"""Check clean-install origin in parent and spawn child, outside the checkout.

Usage: python /path/to/check_installed.py /absolute/venv/root
"""

import multiprocessing
import sys
from pathlib import Path


def origin(expected):
    import hp437b

    actual = Path(hp437b.__file__).resolve()
    assert actual.is_relative_to(Path(expected).resolve()), actual
    assert "site-packages" in actual.parts, actual
    return str(actual)


def child(pipe, expected):
    pipe.send(origin(expected))
    pipe.close()


def main():
    expected = sys.argv[1]
    actual = origin(expected)
    context = multiprocessing.get_context("spawn")
    parent, other = context.Pipe()
    process = context.Process(target=child, args=(other, expected))
    process.start()
    other.close()
    try:
        assert parent.poll(10)
        assert parent.recv() == actual
        process.join(5)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()
        process.close()
    print(f"Installed parent/spawn origin verified: {actual}")


if __name__ == "__main__":
    main()
