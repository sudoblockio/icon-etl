#  MIT License
#
#  Copyright (c) 2021 Richard Mah (richard@geometrylabs.io) & Geometry Labs (geometrylabs.io)
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of
#  this software and associated documentation files (the "Software"), to deal in
#  the Software without restriction, including without limitation the rights to
#  use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
#  the Software, and to permit persons to whom the Software is furnished to do so,
#  subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
#  FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
#  IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
#  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from blockchainetl_common.jobs.exporters.console_item_exporter import (
    ConsoleItemExporter,
)


def create_item_exporter(output, kafka_settings):
    item_exporter_type = determine_item_exporter_type(output)
    if item_exporter_type == ItemExporterType.PUBSUB:
        from blockchainetl_common.jobs.exporters.google_pubsub_item_exporter import (
            GooglePubSubItemExporter,
        )

        item_exporter = GooglePubSubItemExporter(
            item_type_to_topic_mapping={
                "block": output + ".blocks",
                "transaction": output + ".transactions",
                "log": output + ".logs",
            }
        )
    elif item_exporter_type == ItemExporterType.POSTGRES:
        from iconetl.jobs.exporters.converters.int_to_decimal_item_converter import (
            IntToDecimalItemConverter,
        )
        from iconetl.jobs.exporters.converters.list_field_item_converter import (
            ListFieldItemConverter,
        )
        from iconetl.jobs.exporters.converters.unix_timestamp_item_converter import (
            UnixTimestampItemConverter,
        )
        from iconetl.jobs.exporters.postgres_item_exporter import PostgresItemExporter
        from iconetl.streaming.postgres_tables import (
            BLOCKS,
            LOGS,
            RECEIPTS,
            TRANSACTIONS,
        )
        from iconetl.streaming.utils.postgres_item_exporter import (
            create_insert_statement_for_table,
        )

        item_exporter = PostgresItemExporter(
            output,
            item_type_to_insert_stmt_mapping={
                "block": create_insert_statement_for_table(BLOCKS),
                "transaction": create_insert_statement_for_table(TRANSACTIONS),
                "log": create_insert_statement_for_table(LOGS),
                "receipts": create_insert_statement_for_table(RECEIPTS),
            },
            converters=[
                UnixTimestampItemConverter(),
                IntToDecimalItemConverter(),
                ListFieldItemConverter("topics", "topic", fill=4),
            ],
        )

    elif item_exporter_type == ItemExporterType.KAFKA:
        from confluent_kafka import Producer
        from confluent_kafka.schema_registry import SchemaRegistryClient
        from confluent_kafka.schema_registry.protobuf import ProtobufSerializer

        from iconetl.jobs.exporters.kafka_item_exporter import KafkaItemExporter
        from iconetl.schemas.protobuf_compiled import blocks_raw_pb2 as blocks_raw
        from iconetl.schemas.protobuf_compiled import logs_raw_pb2 as logs_raw
        from iconetl.schemas.protobuf_compiled import (
            transactions_raw_pb2 as transactions_raw,
        )

        if kafka_settings["enable_schema_registry"]:
            registry_client = SchemaRegistryClient(
                {"url": kafka_settings["schema_registry_url"]}
            )

            serializers = {
                "block": ProtobufSerializer(
                    blocks_raw.BlockRaw,
                    registry_client,
                    conf={"auto.register.schemas": True},
                ),
                "log": ProtobufSerializer(
                    logs_raw.LogRaw,
                    registry_client,
                    conf={"auto.register.schemas": True},
                ),
                "transaction": ProtobufSerializer(
                    transactions_raw.TransactionRaw,
                    registry_client,
                    conf={"auto.register.schemas": True},
                ),
            }

        else:
            serializers = None

        producer = Producer(
            {
                "bootstrap.servers": output,
                "compression.codec": kafka_settings["compression_type"],
            }
        )

        item_exporter = KafkaItemExporter(
            producer,
            kafka_settings["topic_map"],
            serializers,
        )

    elif item_exporter_type == ItemExporterType.CONSOLE:
        item_exporter = ConsoleItemExporter()
    else:
        raise ValueError("Unable to determine item exporter type for output " + output)

    return item_exporter


def determine_item_exporter_type(output):
    if output is not None and output.startswith("projects"):
        return ItemExporterType.PUBSUB
    elif output is not None and output.startswith("postgresql"):
        return ItemExporterType.POSTGRES
    elif output is None or output == "console":
        return ItemExporterType.CONSOLE
    else:
        return ItemExporterType.KAFKA


class ItemExporterType:
    PUBSUB = "pubsub"
    POSTGRES = "postgres"
    CONSOLE = "console"
    KAFKA = "kafka"
    UNKNOWN = "unknown"
