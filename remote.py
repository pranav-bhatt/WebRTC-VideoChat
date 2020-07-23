import asyncio
from rtcbot import Websocket, RTCConnection, CVCamera, CVDisplay, Speaker, Microphone

flag = 0
camera1 = CVCamera(cameranumber=0)
camera2 = CVCamera(cameranumber=2)
mic = Microphone()
display = CVDisplay()
speaker = Speaker()

# For this example, we use just one global connection
conn = RTCConnection()
conn.video.putSubscription(camera1)
conn.audio.putSubscription(mic)
display.putSubscription(conn.video.subscribe())
speaker.putSubscription(conn.audio.subscribe())

async def receiver():
    global flag
    while True:
        if flag:
            frameSubscription = camera2.subscribe()
        else:
            frameSubscription = camera1.subscribe()
        frame = await frameSubscription.get()
        conn.video.put_nowait(frame)

@conn.subscribe
def onMessage(msg):  # Called when each message is sent
    global flag
    flag = not flag
    print("Got message:", msg, flag)

# Connect establishes a websocket connection to the server,
# and uses it to send and receive info to establish webRTC connection.
async def connect():
    ws = Websocket("https://2d2dda3cbc5e.ngrok.io/InventoTest12")
    remoteDescription = await ws.get()
    robotDescription = await conn.getLocalDescription(remoteDescription)
    ws.put_nowait(robotDescription)
    print("Started WebRTC")
    await ws.close()


asyncio.ensure_future(connect())
asyncio.ensure_future(receiver())
try:
    asyncio.get_event_loop().run_forever()
finally:
    display.close()
    speaker.close()
    mic.close()
    camera1.close()
    camera2.close()
    conn.close()