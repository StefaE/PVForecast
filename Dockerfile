FROM python:3.12-bookworm

WORKDIR /usr/src/app

RUN apt-get -y update && apt-get install -y libhdf5-dev && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

CMD [ "python", "./PVForecasts.py" ]
