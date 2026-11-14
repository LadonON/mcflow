package dev.mcflow.client;

/** A command that can't run as asked. The message goes back to mcflow-server as-is. */
final class CommandException extends RuntimeException {
    CommandException(String message) {
        super(message);
    }
}
