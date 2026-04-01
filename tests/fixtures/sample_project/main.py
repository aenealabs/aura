import hashlib


class DataProcessor:
    def calculate_checksum(self, data):
        # VULNERABILITY: Insecure hash function used
        return hashlib.sha1(data.encode()).hexdigest()


class ResultStore:
    def save_data(self, checksum, result):
        pass
