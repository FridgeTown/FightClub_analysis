# FightClub Analysis
## About
FightClub 실시간 WebRTC 스트리밍 동작 분석 애플리케이션입니다.


![](https://img.shields.io/badge/-MediaPipe-0097A7.svg?&style=flat&logo=MediaPipe&logoColor=white)
![](https://img.shields.io/badge/-YOLOv8-4334eb.svg?&style=flat&logoColor=white)
![](https://img.shields.io/badge/-OpenCV-5C3EE8.svg?&style=flat&logo=OpenCV&logoColor=white)
![](https://img.shields.io/badge/-FastAPI-009688.svg?&style=flat&logo=FastAPI&logoColor=white)
![](https://img.shields.io/badge/-Redis-FF4438.svg?&style=flat&logo=Redis&logoColor=white)

## Getting Started
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
Need to be cloned directly and installed after changing the settings. version conflict issue with livekit and Mediapipe. 
```bash
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
```bash
## after clone and change setting, install packages
$ cd python-sdks/livekit-api
$ pip install .
$ cd ../livekit-rtc
$ pip install .
```
- You'll probably see the message 'OSError' when you run it.
```
Traceback (most recent call last):
...
OSError: dlopen 
...
/.venv/lib/python3.12/site-packages/livekit/rtc/resources/liblivekit_ffi.dylib' (no such file)
```
- Then, You will need to download the appropriate [liblivekit_ffi.dylib](https://github.com/livekit/rust-sdks/releases) asset for your OS environment move it to
  - /.venv/lib/python3.12/site-packages/livekit/rtc/resources/
### Set .env file
- create `.env` file like `.env.secret`
```env
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```
### Start
```bash
## start Mediapipe Motion Analysis
$ python main.py

## start sse server
$ python server.py
```
