# gRPC API Examples

This project contains the examples for possible API design alternatives. The
goal is to evaluate following aspects:

1. Usability;
2. Migration cost;
3. Engineer cost.

## What does the example do?

The example is a web crawler that starts crawling from `https://www.google.com`.
It includes multiple I/O operation, and non-trivial synchronization between
request and response. All alternatives can demonstrate their strength and
weakness.
