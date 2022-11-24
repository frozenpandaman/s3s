FROM python:3

WORKDIR /usr/src/app

# Install python 3 dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create dummy config file
RUN touch config.txt

# Run s3s in monitoring mode and checks for & uploads any battles/jobs present on SplatNet 3 that haven't yet been uploaded.
CMD [ "python", "./s3s.py", "-M", "-r" ]
