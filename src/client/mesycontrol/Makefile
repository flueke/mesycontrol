.PHONY: all

all: resources.py mesycontrol_pb2.py

resources.py: resources.qrc
	pyrcc4 -o resources.py resources.qrc

mesycontrol_pb2.py: ../../mesycontrol.proto
	protoc -I ../../ --python_out=./ ../../mesycontrol.proto
