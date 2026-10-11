# Field-unit image: Ultralytics' Jetson image (PyTorch + TensorRT) plus the MQTT client,
# so the boot service needs nothing installed by hand. The repo is mounted at /work at run time.
FROM ultralytics/ultralytics:8.4.175-jetson-jetpack6
RUN pip install --no-cache-dir "paho-mqtt>=2.0"
WORKDIR /work/jetson
CMD ["python", "scan.py"]
