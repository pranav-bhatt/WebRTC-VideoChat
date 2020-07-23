"""
from aiohttp import web
import asyncio

routes = web.RouteTableDef()

from rtcbot import RTCConnection, Websocket

ws = None

# Serve the RTCBot javascript library at /rtcbot.js
@routes.get("/rtcbot.js")
async def rtcbotjs(request):
    return web.Response(content_type="application/javascript", text=getRTCBotJS())

# This sets up the connection
@routes.get("/ws")
async def websocket(request):
    global ws
    ws = Websocket(request)
    print("Robot Connected")
    await ws  # Wait until the websocket closes
    print("Robot disconnected")
    return ws.ws

# Called by the browser to set up a connection
@routes.post("/connect")
async def connect(request):
    global ws
    if ws is None:
        raise web.HTTPInternalServerError("There is no robot connected")
    clientOffer = await request.json()
    # Send the offer to the robot, and receive its response
    ws.put_nowait(clientOffer)
    robotResponse = await ws.get()
    return web.json_response(robotResponse)


@routes.get("/")
async def index(request):
    return web.Response(
        content_type="text/html",
        text=r""""""
    <html>
        <head>
            <title>RTCBot: Browser Audio & Video</title>
            <script src="/rtcbot.js"></script>
        </head>
        <body style="text-align: center;padding-top: 30px;">
            <video autoplay playsinline controls></video> <audio autoplay></audio>
            <button type="button" id="mybutton">Change camera</button>
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

                    // POST the information to https://rtcbot.dev/InventoTest12
                    let response = await fetch("https://rtcbot.dev/InventoTest12", {
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
    """""",
    )


async def cleanup(app):
    global ws
    if ws is not None:
        c = ws.close()
        if c is not None:
            await c


app = web.Application()
app.add_routes(routes)
app.on_shutdown.append(cleanup)
web.run_app(app)
"""
import asyncio
import aiohttp
from aiohttp import web
from rtcbot import getRTCBotJS

routes = web.RouteTableDef()

websockets = {}

MSG_MAX = 8*1024


async def websocketHandler(request):
    cid = request.match_info['cid']
    if cid in websockets:
        return web.HTTPConflict(text="Already have a connection here")

    ws = web.WebSocketResponse(max_msg_size=MSG_MAX, heartbeat=60.0)
    await ws.prepare(request)
    websockets[cid] = {"ws": ws, "recv": None}
    print(f'({len(websockets)}) {cid}: connection opened')
    try:
        msg = await ws.receive_str()
        if websockets[cid]["recv"] is not None:
            websockets[cid]["recv"].put_nowait(msg)
    except:
        # Clear the queue
        if websockets[cid]["recv"] is not None:
            try:
                websockets[cid]["recv"].put_nowait("")
            except:
                pass

    del websockets[cid]
    print(f'({len(websockets)}) {cid}: connection closed')


async def queueTimeout(ws):
    await asyncio.sleep(10)
    if not ws.closed:
        await ws.close()


@routes.post("/{cid}")
async def postDescription(request):
    cid = request.match_info['cid']
    # We have an active websocket! let's send the description
    content = await request.content.read()
    if not cid in websockets:
        return web.HTTPNotFound(text="No connection is active here")
    q = asyncio.Queue(1)
    websockets[cid]["recv"] = q
    asyncio.ensure_future(queueTimeout(websockets[cid]["ws"]))

    import json
    # content = json.loads(content)
    await websockets[cid]["ws"].send_str(str(content, 'utf-8'))
    response = await q.get()
    return web.Response(content_type="application/json", text=response)


@routes.get("/favicon.ico")
async def favicon(request):
    return web.HTTPNotFound()


@routes.get("/rtcbot.js")
async def rtcbotjs(request):
    return web.Response(content_type="application/javascript", text=getRTCBotJS())


@routes.get("/{cid}")
async def connectionHandler(request):
    if "Connection" in request.headers and request.headers["Connection"] == "Upgrade":
        return await websocketHandler(request)
    return await guiHandler(request)


@routes.get("/")
async def index(request):
    return web.HTTPFound('https://rtcbot.readthedocs.io/en/latest/examples/mobile/README.html#rtcbot-dev')


async def guiHandler(request):
    cid = request.match_info['cid']
    if not cid in websockets:
        return web.Response(content_type="text/html",
                            text=f"""
<html>
    <head>
        <title>{cid} - rtcbot.dev</title>
    </head>
    <body style="text-align: center">
        <h1>{cid}</h1>
        <h3>There is no connection active here</h3>
    </body>
</html>
    """)

    # There is an active connection!

    return web.Response(content_type="text/html",
                        text="""
<html>
        <head>
            <title>%s - rtcbot.dev</title>
            <script src="/rtcbot.js"></script>
        </head>
        <body style="text-align: center;padding-top: 30px;">
            <h1>%s</h1>
            <p>There is a websocket connection active, either click connect below, or run a POST request to https://rtcbot.dev/%s </p>
            <video autoplay playsinline controls></video> <audio autoplay></audio>
            <br/><br/>
            <button onclick="connect()">Connect</button>
            <br/><br/>
            <button type="button" id="mybutton">Change camera</button>
            <br/><br/>
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

                    // POST the information to https://rtcbot.dev/InventoTest12
                    let response = await fetch("/%s", {
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
    """ % (cid, cid, cid, cid))

app = web.Application(client_max_size=MSG_MAX)
app.add_routes(routes)
web.run_app(app, port=1452)
