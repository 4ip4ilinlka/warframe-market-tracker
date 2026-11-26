# PyInstaller spec: one-file windowed exe.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("wfmt/static", "wfmt/static")]
binaries = []
hiddenimports = collect_submodules("uvicorn") + collect_submodules("winrt")
for pkg in ("windows_toasts",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run_wfmt.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "respx"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WFMarketTracker",
    console=False,
    upx=False,
    debug=False,
)
