class RessourceNotFound(Exception):
    def __init__(self, message="Ressource not found -> Please check the identifier and try it again"):
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

class DomainNotRunning(Exception):
    def __init__(self, message="Requested Domain is not running"):
        self.message = message
        super().__init__(self.message)

class DomainAlreadyRunning(Exception):
    def __init__(self, message="Requested Domain is already running"):
        self.message = message
        super().__init__(self.message)
