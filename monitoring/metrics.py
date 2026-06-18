import time
from monitoring.logger import logger


class MetricsCollector:
    """Tracks performance and operational latency counters."""
    def __init__(self):
        self.metrics = {}

    def track_duration(self, metric_name):
        class DurationTracker:
            def __init__(self, collector, name):
                self.collector = collector
                self.name = name
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.collector.record(self.name, duration)
                status = "success" if exc_type is None else "error"
                logger.info(f"Performance Metric: {self.name} completed in {duration:.4f}s with status: {status}")
                
        return DurationTracker(self, metric_name)

    def record(self, metric_name, value):
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)

    def get_average(self, metric_name):
        values = self.metrics.get(metric_name, [])
        if not values:
            return 0.0
        return sum(values) / len(values)


metrics = MetricsCollector()
