# OpenDCDiag

OpenDCDiag is an open-source project designed to identify defects and
bugs in CPUs. It consists of a set of tests built around a
sophisticated CPU testing framework. OpenDCDiag is primarily intended
for, but not limited to, Data Center CPUs.

## License

OpenDCDiag is released under the [Apache 2.0](LICENSE) license. The
OpenDCDiag framework includes some source code from other projects,
released under different licenses.  See
[LICENSE.3rdparty](LICENSE.3rdparty) for more details.

## Building OpenDCDiag

### Prerequisites

#### Ubuntu

OpenDCDiag has been built and tested on Ubuntu 21.04 and 21.10.
Before building, the following prerequisites must be installed.

```console
sudo apt-get install gcc g++ cmake libeigen3-dev libboost-all-dev libzstd-dev zlib1g-dev libgtest-dev meson
```

#### Fedora

OpenDCDiag has been built and tested on Fedora 33 and 34.
Before building, the following prerequisites must be installed.

```console
sudo dnf install -y boost-devel eigen3-devel gcc gcc-c++ git gtest-devel meson zlib-devel libzstd-devel
```

### Building

OpenDCDiag is built with the [Meson Build
System](https://mesonbuild.com/) and the [Ninja](https://ninja-build.org/)
backend. Meson >= 1.3 and a C++23-capable compiler (GCC >= 12) are required.

#### Prerequisites recap

The packages listed under the platform sections above are sufficient, but note
two specifics that commonly trip up fresh checkouts:

- **Eigen**: OpenDCDiag depends on **Eigen >= 5.0**. Most distros still ship
  Eigen 3.x (e.g. `libeigen3-dev`/`eigen3-devel` provides 3.3.x). When the
  system Eigen is too old, the build falls back to the **bundled Eigen 5.0.1
  source tree under `third-part/`** (see `tests/cpu/meson.build`). That tree is
  a git submodule, so it must be fetched before the first build — see the next
  section.
- **No `.gitmodules` in this repo**: `opendcdiag/` is itself checked out as a
  git submodule of a parent repository, and its `third-part` (Eigen) entry is a
  nested submodule whose config lives in the parent. As a result, a plain
  `git submodule update --init` run *inside* `opendcdiag/` does **not** discover
  `third-part/`. You must either init it from the parent repo, or init it by
  path from here.

#### Initialize the bundled Eigen source (third-part/)

Run one of the following before the first build. `third-part/` is in
`.gitignore` (fetched, not committed), so a fresh clone leaves it empty and the
build will `assert`-fail without it (unless a system Eigen >= 5.0 is present).

```console
# Option A: from the parent repository (init all nested submodules)
cd .. && git submodule update --init --recursive opendcdiag/third-part

# Option B: from inside opendcdiag/, init by path
git submodule update --init third-part

# Option C: no git history — clone Eigen 5.0.1 directly
git clone --depth 1 --branch 5.0.1 https://gitlab.com/libeigen/eigen.git third-part
```

If the build complains `Bundled Eigen 5.0 source not found under third-part/`,
you skipped this step.

#### Native build (x86_64 or ARM64)

```console
meson setup builddir --buildtype=release
ninja -C builddir
```

On AArch64 hosts, Meson auto-applies `-march=armv8.1-a -mtune=generic`
(see `meson.build`), matching e.g. the Kunpeng 920 (ARMv8.1-A). No extra flags
are needed.

#### Cross-compile for ARM64 from x86

```console
sudo apt-get install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu   # Ubuntu
meson setup builddir --cross-file meson-cross-arm64.ini --buildtype=release
ninja -C builddir
```

#### Verify the build

```console
./builddir/opendcdiag --version
./builddir/opendcdiag --list
```

A clean release build compiles all targets with no errors. A handful of
warnings are expected and harmless on ARM64:
`sysv_abi attribute ignored` (x86-only calling convention in
`framework/sandstone.cpp`), `[[assume(...)]] attribute ignored` (GCC 12
limitation), and any remaining `-Wunused` notes in
`framework/device/cpu/arm64/`.

#### Full-load, continuous run

The `-T forever` option loops indefinitely; `-n 0` uses one thread per logical
CPU for full load; `--ignore-os-error --ignore-timeout` keep it running past
errors. See `framework/sandstone_opts.cpp` for the full option set.

```console
./builddir/opendcdiag -T forever -n 0 --ignore-os-error --ignore-timeout -o /dev/null -q
```

## Contributions

The OpenDCDiag project welcomes contributions and pull requests.
Please see [Contributing to OpenDCDiag](CONTRIBUTING.md) for more
details.

## Code of Conduct

The OpenDCDiag project has adopted the Contributor's Covenant as its [Code of
Conduct][coc]. The project requires contributors and users to follow our Code
of Conduct, both in letter and in spirit.

[coc]: CODE_OF_CONDUCT.md

## Writing Tests

The OpenDCDiag framework is designed to make the creation of new CPU
tests as simple as possible. It takes care of much of the boiler
plate code CPU tests need, e.g., test life cycle, threading model, CPU
feature identification, random number generation, etc. This allows test
authors to concentrate on the specific test functionality that
interests them. A detailed guide to writing new OpenDCDiag tests is
presented in [A Guide to Writing OpenDCDiag
tests](docs/writing_tests.md).

## Intel® Data Center Diagnostic Tool

Intel provides a tool called the
[Intel® Data Center Diagnostic Tool](https://www.intel.com/content/www/us/en/support/articles/000058107/processors/intel-xeon-processors.html)
for verifying the functionality of all cores within an Intel® Xeon®
processor.  Intel Data Center Diagnostic Tool is built using the OpenDCDiag framework and is
freely downloadable.  It is not however open-source and it is designed for
use with Intel Xeon processors only. The Intel Data Center
Diagnostic Tool contains additional tests that are not part of the OpenDCDiag project.
