# Third-party notices

The repository retains its Apache License 2.0. Imported Forge source files
retain their original attribution and contents. The high-level executable is
built from the existing Forge HTTP node and SportClientController.

## Forge robot source

- Source: https://gitlab.ex-ai.cn/PhyAgentOS/framework/robots/unitree_go2
- Commit: 7cda218272557b9f7171ab7573ce9bf8eed54897
- Inventory: packaging/forge-source.json (91 original files)
- Verification: python3 packaging/verify_source.py

## Unitree SDK2 Python

- Source: https://github.com/unitreerobotics/unitree_sdk2_python
- Commit: 814556d15970dd2ecf1c9984e845ca02ab07e206
- Path: packaging/vendor/unitree_sdk2_python
- License: BSD-3-Clause; see that directory's LICENSE.

## Eclipse Cyclone DDS

- Source: https://github.com/eclipse-cyclonedds/cyclonedds
- Commit: 9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd (0.10.2)
- Path: packaging/vendor/cyclonedds
- License: EPL-2.0 OR BSD-3-Clause; original LICENSE and NOTICE.md retained.
- The tracing buffer fix is backported from upstream commit
  5041f3560c088c99e5088b2b8520b69169621196; details and patch digest are in
  packaging/dependencies.json.

## Runtime dependencies

The executable bundles Python (PSF), Dora (Apache-2.0), PyArrow (Apache-2.0),
PyYAML (MIT), Cyclone DDS Python (EPL-2.0 OR BSD-3-Clause) and their required
runtime components. The isolated dependency lock is packaging/uv.lock.
PyInstaller is a build tool with its bootloader redistribution exception.

## Unitree SDK2 Python license text

BSD 3-Clause License

Copyright (c) 2016-2024 HangZhou YuShu TECHNOLOGY CO.,LTD. ("Unitree Robotics")
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
