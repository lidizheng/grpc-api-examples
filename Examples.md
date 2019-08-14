# Definition For Each Set of API

* Current: Existing gRPC Python API
* Option 1: Async API similar to existing gRPC Python API
* Option 2: Brand new Async API
* Ideal: The most idealistic `asyncio` approach

## Motivation
* Asynchronous processing perfectly fits IO-intensive gRPC use cases;
* Resolve a long-living design flaw of thread exhaustion problem;
* Performance is much better than the multi-threading model.

# Client Side Examples
## Unary-Unary Call

### Current API

```Python
with grpc.insecure_channel('localhost:50051') as channel:
    stub = helloworld_pb2_grpc.GreeterStub(channel)
    response = stub.Hi(...)
```

### Option 1 / Option 2

```Python
async with grpc.insecure_channel('localhost:50051') as channel:
    stub = helloworld_pb2_grpc.GreeterStub(channel)
    response = await stub.Hi(...)
```

### Ideal

```Python
helloworld_protos = grpc.proto('helloworld.proto')
response = await helloworld_protos.Hi('localhost:50051', request)
```

# Stream-Stream Call

### Current API

```Python
class RequestIterator:

    def __init__(self):
        self._queue = queue.Queue()

    def send(self, message):
        self._queue.put(message)

    def __iter__(self):
        return self

    def __next__(self):
        return self._queue.get(block=True)

request_iterator = RequestIterator()
response_iterator = stub.StreamingHi(request_iterator)

# In sending thread
request_iterator.send(proto_message)

# In receiving thread
for response in response_iterator:
    process(response)
```

A special advanced usage that can shrink the LOC:

```Python
request_queue = queue.Queue()
response_iterator = stub.StreamingHi(iter(request_queue.get, None))

# In sending thread
request_iterator.send(proto_message)

# In receiving thread
for response in response_iterator:
    process(response)
```

### Option 1

```Python
class RequestIterator:

    def __init__(self):
        self._queue = asyncio.Queue()

    def send(self, message):
        self._queue.put(message)

    def __iter__(self):
        return self

    async def __anext__(self):
        return await self._queue.get()

request_iterator = RequestIterator()
response_iterator = stub.StreamingHi(request_iterator)

# In sending thread
await request_iterator.send(proto_message)

# In receiving thread
async for response in response_iterator:
    process(response)
```

### Option 2

```Python
call = stub.StreamingHi()

# In sending thread
await call.send(proto_message)

# In receiving thread
try:
    response = await call.receive()
    process(response)
except grpc.EOF:
    pass
```

### Ideal

```Python
helloworld_protos = grpc.proto('helloworld.proto')
call = await helloworld_protos.StreamingHi('localhost:50051')

# In sending thread
await call.send(proto_message)

# In receiving thread
try:
    while True:
        response = await call.receive()
        process(response)
except grpc.EOF:
    pass
```

# Server Side Example

## Server Creation

### Current API

```Python
server = grpc.server(ThreadPoolExecutor(max_workers=10))
server.add_insecure_port(':50051')
helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
server.start()
server.wait_for_termination()
```

### Option 1 / Option 2 / Ideal

```Python
server = grpc.server()
server.add_insecure_port(':50051')
helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
server.start()
await server.wait_for_termination()
```

## Unary-Unary Handler

### Current API

```Python
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def Hi(self, request, context):
        return ...
```

### Option 1 / Option 2 / Ideal

```Python
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    async def Hi(self, request, context):
        response = await some_io_operation
        return response
```

## Stream-Stream Handler

### Current API

```Python
class ResponseIterator:

    def __init__(self):
        self._queue = queue.Queue()

    def send(self, message):
        self._queue.put(message)

    def __iter__(self):
        return self

    def __next__(self):
        return self._queue.get()

def streaming_hi_worker(request_iterator, response_iterator):
    for request in request_iterator:
        if request.needs_respond:
            response_iterator.send(response)

class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def StreamingHi(self, request_iterator, context):
        response_iterator = ResponseIterator()
        background_thread = threading.Thread(target=streaming_hi_worker)
        background_thread.daemon = True
        background_thread.start()
        return response_iterator
```

The most simple case of streaming handler is the responses one-to-one mapped to
the requests.

```Python
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def StreamingHi(self, request_iterator, context):
        for request in request_iterator:
            yield response
```

### Option 1

```Python
class ResponseIterator:

    def __init__(self):
        self._queue = asyncio.Queue()

    def send(self, message):
        self._queue.put(message)

    def __iter__(self):
        return self

    async def __anext__(self):
        return await self._queue.get()

def streaming_hi_worker(request_iterator, response_iterator):
    async for request in request_iterator:
        if request.needs_respond:
            await response_iterator.send(response)

class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def StreamingHi(self, request_iterator, context):
        response_iterator = ResponseIterator()
        background_thread = threading.Thread(target=streaming_hi_worker)
        background_thread.daemon = True
        background_thread.start()
        return response_iterator
```

```Python
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    async def StreamingHi(self, request_iterator, context):
        async for request in request_iterator:
            yield response
```

### Option 2 / Ideal

```Python
class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def StreamingHi(self, context):
        while True:
            request = await context.receive()
            if request.needs_respond:
                await context.send(response)
```

# Generated File

## Current / Option 1

Keep the generated file untouched. Only swap the underlying implementation.

```Python
import helloworld_pb2
import helloworld_pb2_grpc
channel = grpc.insecure_channel('localhost:50051'):
stub = helloworld_pb2_grpc.GreeterStub(channel)
...
```

## Option 2

The new generated file is clean, and potentially enables us to add breaking
changes. But currently, it provides almost zero value.

```Python
import helloworld_pb2_grpc_async
channel = grpc.insecure_channel('localhost:50051'):
stub = helloworld_pb2_grpc_async.GreeterStub(channel)
```
