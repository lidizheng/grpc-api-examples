.PHONY: all clean

all: ./current/proto/*.py ./current/data

./proto/scraping_pb2.py:
./proto/scraping_pb2_grpc.py:
	python -m grpc_tools.protoc -I . --python_out=proto --grpc_python_out=proto proto/scraping.proto

./current/proto/*.py: ./proto/scraping_pb2.py ./proto/scraping_pb2_grpc.py
	rm -rf ./current/proto
	cp -r ./proto/proto current/proto

./current/data:
	mkdir -p ./current/data

clean:
	rm -rf ./proto/scraping_pb2.py
	rm -rf ./proto/scraping_pb2_grpc.py
	rm -rf ./current/proto
	rm -rf ./current/data
