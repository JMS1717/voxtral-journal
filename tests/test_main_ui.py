from app.main import build_demo


def test_gradio_demo_builds():
    demo = build_demo()
    assert demo.blocks

