# FightClub Analysis
## Install
### Set virtual environment
```
$ python -m venv .venv
$ source .venv/bin/activate
```
### Install packages
```
$ pip install --upgrade pip
$ pip install -r requirements.txt
```
### Clone and Change setting livekit setup
Need to be cloned directly and installed after changing the settings. version conflict issue with Mediapipe. 
```
$ git clone https://github.com/livekit/python-sdks.git
```
- change setting in `/python-sdks/livekit-api/setup.py`
```python
## /python-sdks/livekit-api/setup.py

# before
install_requires=[
  ...
  "protobuf>=3",
  ...
],

# after
install_requires=[
  ...
  "protobuf>=4.25.3,<5",
  ...
],
```
- change setting in `/python-sdks/livekit-protocol/setup.py`
```python
## /python-sdks/livekit-protocol/setup.py

# before
install_requires=[
    "protobuf>=3",
    "types-protobuf>=4,<5",
],

# after
install_requires=[
    "protobuf>=4.25.3,<5",
    "types-protobuf>=4,<5",
],
```
- change setting in `/python-sdks/livekit-rtc/setup.py`
```python
## /python-sdks/livekit-rtc/setup.py

# before
install_requires=["protobuf>=5.26.1" ...],
# after
install_requires=["protobuf>=4.25.3,<5" ...],
```
### Install livekit packages
```
// after clone and change setting, install packages
$ cd python-sdks/livekit-api
$ pip install .
$ cd ../livekit-rtc
$ pip install .
```
- After installation and running, probably you will see an `OSError` message.
```
Traceback (most recent call last):
...
OSError: dlopen 
...
/.venv/lib/python3.12/site-packages/livekit/rtc/resources/liblivekit_ffi.dylib' (no such file)
```
- Then, You will need to download the appropriate [liblivekit_ffi.dylib](https://github.com/livekit/rust-sdks/releases) asset for your OS environment and move it to the appropriate location.
  - /.venv/lib/python3.12/site-packages/livekit/rtc/resources/
### Set .env file
- create .env file like .env.secret
```env
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```
### Start
```
$ python main.py
```