from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auth_storage_keys_are_consistent():
    client = (ROOT / "frontend" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    auth = (ROOT / "frontend" / "src" / "store" / "auth.ts").read_text(encoding="utf-8")

    assert 'localStorage.removeItem("user")' in client
    assert 'localStorage.removeItem("username")' not in client
    assert 'localStorage.getItem("user")' in auth


def test_vite_splits_large_vendor_chunks():
    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert "manualChunks" in config
    assert "element-plus" in config
    assert "vue-vendor" in config


def test_element_plus_is_registered_without_full_library_plugin():
    main = (ROOT / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")

    assert "app.use(ElementPlus" not in main
    assert "ElementPlusIconsVue" not in main
    assert "app.component(\"ElButton\"" in main
