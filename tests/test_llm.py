import pytest

from proofpost.brand import Brand
from proofpost.llm import hook_fn
from proofpost.models import Platform, Review
from proofpost.pipeline import run


def fake_post(line):
    return lambda url, headers, body: {"choices": [{"message": {"content": line}}]}


def test_llm_writes_hook_but_never_the_quote():
    hook = hook_fn("ollama", Brand(), post=fake_post("Small batches, big flavour."))
    r = Review(id="1", text="The aroma is fresh and the taste is smooth every morning.", rating=5)
    res = run([r], Brand(), platforms=(Platform.LINKEDIN,), hook_fn=hook)
    assert res.posts[0].text.startswith("Small batches, big flavour.")
    assert "“The aroma is fresh and the taste is smooth every morning.”" in res.posts[0].text


@pytest.mark.parametrize("bad", ["Guaranteed 100% results!", "“quote” inside", "#hashtag hook",
                                 "", "x" * 120])
def test_unsafe_hooks_fall_back_to_template(bad):
    assert hook_fn("ollama", Brand(), post=fake_post(bad))("taste", "instagram") is None


def test_failure_falls_back():
    def boom(*a):
        raise TimeoutError

    assert hook_fn("ollama", Brand(), post=boom)("taste", "x") is None


def test_hosted_provider_needs_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        hook_fn("groq", Brand())
