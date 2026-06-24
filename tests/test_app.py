from src.app import add, greet


def test_add():
    assert add(2, 3) == 5


def test_greet():
    assert greet("DevOps") == "Hello, DevOps!"
