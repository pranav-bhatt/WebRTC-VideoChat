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

                    console.log("posting offer");

                    // POST the information to https://rtcbot.dev/InventoTest12
                    let response = await fetch("/%s", {
                        method: "POST",
                        cache: "no-cache",
                        body: JSON.stringify(offer)
                    });

                    console.log("received response");

                    await conn.setRemoteDescription(await response.json());

                    console.log("Ready!");
                }

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
