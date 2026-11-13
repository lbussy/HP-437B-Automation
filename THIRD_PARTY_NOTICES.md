# Licensing scope and third party notices

The [MIT License](LICENSE) applies to original documents, notes, designs, code, and other work owned by lbussy, and to original contributions supplied under that license. It does not relicense third-party material contained in or alongside that work. Existing third-party copyrights, license terms, attribution requirements, and other notices remain in effect.

## Publisher manuals

The following publisher originals retain their embedded copyright and licensing notices. They are excluded from this project's MIT grant.

| File | Publisher source |
| --- | --- |
| [HP 437B Operating Manual 00437-90047](output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf) | [Keysight official manual](https://www.keysight.com/us/en/assets/9018-40507/user-manuals/9018-40507.pdf) |
| [HP 437B Service Manual 00437-90076](output/pdf/hp-437b-8482a/HP-437B-Service-Manual-00437-90076.pdf) | [Keysight official manual](https://www.keysight.com/us/en/assets/9018-05110/service-manuals/9018-05110.pdf) |
| [8480 Series Operating and Service Manual 08481-90173](output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf) | [Keysight official manual](https://www.keysight.com/us/en/assets/9018-04931/service-manuals/9018-04931.pdf) |

The [download manifest](output/pdf/hp-437b-8482a/download-manifest.json) records the original download locations, editions, sizes, and SHA-256 hashes. Preserve the original files and all embedded notices. Local possession and an official download URL do not establish a separate grant of redistribution rights; no separate redistribution permission is recorded in this collection.

## Individual calibration records

The complete [437B and 8482A calibration records](docs/EQUIPMENT.md#individual-calibration-records), issued by DXCONNECTION / Valley Precision Instrument Calibration Services and supplied by the equipment owner, retain their embedded notices and are excluded from the MIT grant. Each certificate permits reproduction in full and requires prior written consent for partial reproduction. The PDFs are preserved in full without modification; the separate [import manifest](output/pdf/hp-437b-8482a/calibration/import-manifest.json) records their provenance and integrity.

## Software dependencies

The package uses ordinary dependencies; their source is obtained through their package distributions. Runtime pins: [PyVISA 1.16.2](https://pypi.org/project/PyVISA/1.16.2/) (MIT), [PyVISA-py 0.8.1](https://pypi.org/project/PyVISA-py/0.8.1/) (MIT), [PyUSB 1.3.1](https://pypi.org/project/PyUSB/1.3.1/) (BSD-3-Clause), and transitive typing_extensions 4.16.0 (PSF-2.0). A separately installed libusb retains its LGPL-2.1-or-later terms. Dependencies and libusb remain separate from this project's MIT grant.

Development pins and transitive versions are in [requirements-dev.lock](requirements-dev.lock). pytest, Ruff, build, setuptools, iniconfig, pluggy, and pyproject_hooks use MIT licenses; Pygments uses BSD-2-Clause; packaging uses Apache-2.0 OR BSD-2-Clause. Package distributions carry the authoritative license notices. R&S VISA is proprietary royalty-free software, not part of this project's MIT grant, and is not bundled here.

Product names and trademarks remain those of their owners. The original copied download manifest describes the earlier download; migration details are recorded separately in [project provenance](docs/PROVENANCE.md).

## Optional PDF report rendering

The optional PDF extra uses ReportLab 5.1.0 under its upstream BSD license, Pillow 13.0.0 under the MIT-CMU license, and charset-normalizer 3.5.2 under the MIT license. Distributions carry their authoritative notices; see the [ReportLab distribution](https://pypi.org/project/reportlab/5.1.0/) and [upstream documentation](https://docs.reportlab.com/). These dependencies are installed separately, not vendored here.

PDFs embed ReportLab's bundled Bitstream Vera font subsets. The original Bitstream Vera copyright/permission notice is copied without alteration from the installed distribution into each report's `font-license.txt` and retained in PDF Subject metadata, including when reports are packaged. The font is not relicensed by this project's MIT grant. No publisher manual or private calibration document is included automatically.

The reporting test parser, pypdf 7.0.1, uses BSD-3-Clause and is pinned only in `requirements-pdf-test.lock`; it is not a runtime dependency.
