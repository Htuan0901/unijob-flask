FROM python:3.12-slim
WORKDIR /home/unijob
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY migrations migrations
COPY desktop desktop
COPY unijob.py config.py boot.sh ./
RUN chmod +x boot.sh
ENV FLASK_APP=unijob.py FLASK_CONFIG=production
EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
