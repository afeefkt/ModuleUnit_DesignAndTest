# Vendored front-end libraries

Served by Streamlit's static file serving (`server.enableStaticServing` in `.streamlit/config.toml`)
at `/app/static/vendor/…`, so flow charts render without internet access. `_common.render_mermaid`
falls back to the jsdelivr CDN only when these files cannot be loaded.

| File | Package | Version | License | SHA-256 |
|---|---|---|---|---|
| `mermaid-10.9.8.min.js` | [mermaid](https://github.com/mermaid-js/mermaid) (`dist/mermaid.min.js`) | 10.9.8 | MIT | `8D607D7EF1D077A8AA202E18E62212BFA992C68BFEABC5CF45D51A128FE6675D` |
| `svg-pan-zoom-3.6.1.min.js` | [svg-pan-zoom](https://github.com/bumbu/svg-pan-zoom) (`dist/svg-pan-zoom.min.js`) | 3.6.1 | BSD-style (`svg-pan-zoom.LICENSE`) | `F463710320089C61D0F57CEC2B886C02DE04E21EB92EBD22EAA327FDF0A6B7C6` |

The mermaid npm package ships no LICENSE file; its `package.json` declares `"license": "MIT"`
(Copyright (c) 2014 - 2022 Knut Sveidqvist).

To update: download the new `dist/*.min.js` from `https://cdn.jsdelivr.net/npm/<package>@<version>/`,
change the file name and the constants in `launcher/_common.py`, and update this table.
