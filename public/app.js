const ws = new WebSocket('ws://localhost:8000/ws');
        
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  // 이미지 업데이트
  document.getElementById('video-feed').src = 'data:image/jpeg;base64,' + data.image;
  
  // 통계 업데이트
  document.getElementById('p1-hook').textContent = data.stats.player1.hook;
  document.getElementById('p1-face').textContent = data.stats.player1.hits.face;
  document.getElementById('p1-body').textContent = data.stats.player1.hits.body;
  document.getElementById('p1-total').textContent = 
      data.stats.player1.hits.face + data.stats.player1.hits.body;
  
  document.getElementById('p2-hook').textContent = data.stats.player2.hook;
  document.getElementById('p2-face').textContent = data.stats.player2.hits.face;
  document.getElementById('p2-body').textContent = data.stats.player2.hits.body;
  document.getElementById('p2-total').textContent = 
      data.stats.player2.hits.face + data.stats.player2.hits.body;
};
let APPLICATION_SERVER_URL = "http://43.201.27.173:6080/";
var LIVEKIT_URL = "wss://openvidufightclubsubdomain.click/";
configureLiveKitUrl();

const LivekitClient = window.LivekitClient;
var room;
let intr;

function configureLiveKitUrl() {
    if (!APPLICATION_SERVER_URL) {
      if (window.location.hostname === "localhost") {
          APPLICATION_SERVER_URL = "http://localhost:6080/";
      } else {
          APPLICATION_SERVER_URL = "https://" + window.location.hostname + ":6443/";
      }
    }
    // If LIVEKIT_URL is not configured, use default value from OpenVidu Local deployment
    if (!LIVEKIT_URL) {
        if (window.location.hostname === "localhost") {
            LIVEKIT_URL = "ws://localhost:7880/";
        } else {
            LIVEKIT_URL = "wss://" + window.location.hostname + ":7443/";
        }
    }
}

async function joinRoom() {
  // Disable 'Join' button
  document.getElementById("join-button").disabled = true;
  document.getElementById("join-button").innerText = "Joining...";

  // Initialize a new Room object
  room = new LivekitClient.Room();

  // Specify the actions when events take place in the room
  // On every new Track received...
  room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, _publication, participant) => {
    if (track.kind === "video") {
      console.log(`Subscribed to video track from: ${participant.identity}`);

      const mediaStream = new MediaStream([track.mediaStreamTrack]);
      const video = document.createElement("video");
      video.srcObject = mediaStream;
      video.muted = true; // 오디오 제외
      video.play();

      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");

      video.addEventListener("loadedmetadata", () => {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;

          intr = setInterval(() => {
              if (!video.videoWidth || !video.videoHeight) {
                  console.error("Video dimensions are not set.");
                  return;
              }

              context.drawImage(video, 0, 0, canvas.width, canvas.height);
              const base64Data = canvas.toDataURL("image/jpeg", 1);

            // console.log(`${participant.identity} Base64 Length: ${base64Data}`);
            ws.send(JSON.stringify({image: base64Data.split(',')[1]}));
            // document.getElementById('video-feed').src = base64Data;
          }, 100); // 100ms 주기로 캡처
      });
  }
  });

  // On every new Track destroyed...
  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track, _publication, participant) => {
      track.detach();
      document.getElementById(track.sid)?.remove();

      if (track.kind === "video") {
          removeVideoContainer(participant.identity);
          clearInterval(intr)
      }
  });

  try {
      // Get the room name and participant name from the form
      const roomName = document.getElementById("room-name").value;
      const userName = document.getElementById("participant-name").value;

      // Get a token from your application server with the room name and participant name
      const token = await getToken(roomName, userName);

      // Connect to the room with the LiveKit URL and the token
      await room.connect(LIVEKIT_URL, token);

      // Hide the 'Join room' page and show the 'Room' page
      document.getElementById("join").hidden = true;
      document.getElementById("room").hidden = false;

  } catch (error) {
      console.log("There was an error connecting to the room:", error.message);
      await leaveRoom();
  }
}

function addTrack(track, participantIdentity, local = false) {
  const element = track.attach();
  element.id = track.sid;

  /* If the track is a video track, we create a container and append the video element to it 
  with the participant's identity */
  if (track.kind === "video") {
      const videoContainer = createVideoContainer(participantIdentity, local);
      videoContainer.append(element);
      appendParticipantData(videoContainer, participantIdentity + (local ? " (You)" : ""));
  } else {
      document.getElementById("layout-container").append(element);
  }
}

async function leaveRoom() {
  // Leave the room by calling 'disconnect' method over the Room object
  await room.disconnect();

  // Back to 'Join room' page
  document.getElementById("join").hidden = false;
  document.getElementById("room").hidden = true;

  // Enable 'Join' button
  document.getElementById("join-button").disabled = false;
  document.getElementById("join-button").innerText = "Join!";
}

window.onbeforeunload = () => {
  room?.disconnect();
};

function generateFormValues() {
  document.getElementById("room-name").value = "Test Room";
  document.getElementById("participant-name").value = "Participant" + Math.floor(Math.random() * 100);
}




async function getToken(roomName, participantName) {
  const response = await fetch(APPLICATION_SERVER_URL + "token", {
      method: "POST",
      headers: {
          "Content-Type": "application/json"
      },
      body: JSON.stringify({
          roomName: roomName,
          participantName: participantName
      })
  });

  if (!response.ok) {
      const error = await response.json();
      throw new Error(`Failed to get token: ${error.errorMessage}`);
  }

  const data = await response.json();
  console.log(data);
  return data.token;
}

function createVideoContainer(participantIdentity, local = false) {
  const videoContainer = document.createElement("div");
  videoContainer.id = `camera-${participantIdentity}`;
  videoContainer.className = "video-container";
  const layoutContainer = document.getElementById("layout-container");

  if (local) {
      layoutContainer.prepend(videoContainer);
  } else {
      layoutContainer.append(videoContainer);
  }

  return videoContainer;
}

function appendParticipantData(videoContainer, participantIdentity) {
  const dataElement = document.createElement("div");
  dataElement.className = "participant-data";
  dataElement.innerHTML = `<p>${participantIdentity}</p>`;
  videoContainer.prepend(dataElement);
}

function removeVideoContainer(participantIdentity) {
  const videoContainer = document.getElementById(`camera-${participantIdentity}`);
  videoContainer?.remove();
}

function removeAllLayoutElements() {
  const layoutElements = document.getElementById("layout-container").children;
  Array.from(layoutElements).forEach((element) => {
      element.remove();
  });
}

// async function httpRequest(method, url, body) {
//   try {
//       const response = await fetch(url, {
//           method,
//           headers: {
//               "Content-Type": "application/json"
//           },
//           body: method !== "GET" ? JSON.stringify(body) : undefined
//       });

//       const responseBody = await response.json();

//       if (!response.ok) {
//           console.error(responseBody.errorMessage);
//           const error = {
//               status: response.status,
//               message: responseBody.errorMessage
//           };
//           return [error, undefined];
//       }

//       return [undefined, responseBody];
//   } catch (error) {
//       console.error(error.message);
//       const errorObj = {
//           status: 0,
//           message: error.message
//       };
//       return [errorObj, undefined];
//   }
// }