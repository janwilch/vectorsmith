"""CLI audit sinks."""

from vectorsmith_cli.observe.sinks import FileSink, HTTPSink, OTLPSink, StdoutSink, build_audit_sink

__all__ = ["FileSink", "HTTPSink", "OTLPSink", "StdoutSink", "build_audit_sink"]
