from aiohttp import web
import asyncio

routes = web.RouteTableDef()

from rtcbot import RTCConnection, getRTCBotJS, CVDisplay, Speaker, CVCamera, Microphone

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

# Serve the RTCBot javascript library at /rtcbot.js
@routes.get("/rtcbot.js")
async def rtcbotjs(request):
    return web.Response(content_type="application/javascript", text=getRTCBotJS())


# This sets up the connection
@routes.post("/connect")
async def connect(request):
    clientOffer = await request.json()
    serverResponse = await conn.getLocalDescription(clientOffer)
    return web.json_response(serverResponse)


@routes.get("/")
async def index(request):
    return web.Response(
        content_type="text/html",
        text=r"""
    <html>
        <head>
            <title>RTCBot: Browser Audio & Video</title>
            <script src="/rtcbot.js"></script>
        </head>
        <body style="text-align: center;padding-top: 30px;">
            <video autoplay playsinline controls></video> <audio autoplay></audio>
            <button type="button" id="mybutton">Click me!</button>
            <p>
            Open the browser's developer tools to see console messages (CTRL+SHIFT+C)
            </p>
            <script>
                var conn = new rtcbot.RTCConnection();

                conn.video.subscribe(function(stream) {
                    document.querySelector("video").srcObject = stream;
                });
                conn.audio.subscribe(function(stream) {
                    document.querySelector("audio").srcObject = stream;
                });

                async function connect() {

                    let streams = await navigator.mediaDevices.getUserMedia({audio: true, video: true});
                    conn.video.putSubscription(streams.getVideoTracks()[0]);
                    conn.audio.putSubscription(streams.getAudioTracks()[0]);

                    let offer = await conn.getLocalDescription();

                    // POST the information to /connect
                    let response = await fetch("/connect", {
                        method: "POST",
                        cache: "no-cache",
                        body: JSON.stringify(offer)
                    });

                    await conn.setRemoteDescription(await response.json());

                    console.log("Ready!");
                }
                connect();

                var mybutton = document.querySelector("#mybutton");
                mybutton.onclick = function() {
                    conn.put_nowait("Button Clicked!");
                };
            </script>
        </body>
    </html>
    """,
    )


async def cleanup(app):
    await conn.close()
    display.close()
    speaker.close()
    mic.close()
    camera1.close()
    camera2.close()


app = web.Application()
app.add_routes(routes)
app.on_shutdown.append(cleanup)
asyncio.ensure_future(receiver())
web.run_app(app)
