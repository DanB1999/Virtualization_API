class ResourceNotFound(Exception):
    def __init__(self, message="Requested Resource not found -> Check identifier"):
        self.message = message
        super().__init__(self.message)

class ArgumentNotFound(Exception):
    def __init__(self, message):
        self.message = message+" -> Search the documentation for the right argument"
        super().__init__(self.message)

class ImageNotFound(Exception):
    def __init__(self, message="Image not found -> Search for spellling mistakes"):
        self.message = message
        super().__init__(self.message)

class APIError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ConnectionFailed(Exception):
    def __init__(self, message="Failed to establish a connection to daemon -> Contact your system administrator"):
        self.message = message
        super().__init__(self.message)

class ResourceNotRunning(Exception):
    def __init__(self, message="Requested resource is not running"):
        self.message = message
        super().__init__(self.message)

class ResourceAlreadyRunning(Exception):
    def __init__(self, message="Requested resource is already running"):
        self.message = message
        super().__init__(self.message)

class ResourceRunning(Exception):
    def __init__(self, message="Requested Resource is still running, please shutoff/stop resource before continue"):
        self.message = message
        super().__init__(self.message)
