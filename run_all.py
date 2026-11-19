from evaluate import evaluate
from dev_tests import DEV_TESTS
from heldout_tests import HELDOUT_TESTS

for name, tests in [("dev", DEV_TESTS), ("heldout", HELDOUT_TESTS)]:
    for retries in (0, 2):
        print(f"=== {name}, retries={retries} ===")
        evaluate(tests, retries)
