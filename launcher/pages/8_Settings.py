"""Settings — where CppUTest lives, plus extra compiler flags for the generated Makefile."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402,F401  (bootstraps env)
from mudmut_core import settings, toolchain  # noqa: E402

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

st.title("⚙️ Settings")
st.caption("Stored in `config/settings.json` (git-ignored). Every run's `03_mut/Makefile` is generated from these values.")

current = settings.get_settings()
st.header("CppUTest")
st.markdown(
    "Folder that contains `include/CppUTest/` and `lib/` (or `lib64/`). Leave empty to auto-detect "
    "(`/usr`, `/usr/local`, `/opt/cpputest`, `~/cpputest`). Windows paths such as `D:\\libs\\cpputest` "
    "are converted to their WSL form."
)
home = st.text_input("CppUTest folder", current["cpputest_home"], placeholder="/opt/cpputest  or  D:\\libs\\cpputest")
flags = st.text_input("Extra compiler flags (optional)", current["extra_cflags"], placeholder="-DUNIT_TEST -O0")

col1, col2 = st.columns(2)
if col1.button("💾 Save", type="primary"):
    settings.save_settings(cpputest_home=home, extra_cflags=flags)
    st.success("Saved. The next build regenerates the Makefile with these values.")
if col2.button("🔍 Check"):
    with st.spinner("Probing…"):
        info = toolchain.find_cpputest(home)
    if info.found:
        st.success(f"CppUTest found at `{info.home}`")
        st.write(f"- include: `{info.include_dir}`\n- lib: `{info.lib_dir}`\n- CppUTestExt: {'✅' if info.has_ext else '❌ (not linked)'}")
    else:
        st.error(info.detail)
        st.markdown(f"Install it in WSL: `{toolchain.APT_INSTALL_CPPUTEST_LCOV}`")

if current["cpputest_home"] and os.environ.get("MUDMUT_CPPUTEST_HOME"):
    st.info("`MUDMUT_CPPUTEST_HOME` is set in the environment and overrides the saved value.")
