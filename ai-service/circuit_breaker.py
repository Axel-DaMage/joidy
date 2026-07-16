import asyncio
import logging
from enum import Enum
from time import time
from typing import Callable, Any

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Operación normal
    OPEN = "OPEN"          # Fallando rápido (fast-fail)
    HALF_OPEN = "HALF_OPEN" # Probando recuperación

class CircuitBreakerError(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time() - self.last_failure_time >= self.recovery_timeout:
                    logger.info("[CircuitBreaker] Probando conexión externa (OPEN -> HALF_OPEN)")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerError("El circuito está OPEN. Fallando rápido para proteger el sistema.")
        
        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            async with self._lock:
                self.failures += 1
                self.last_failure_time = time()
                if self.failures >= self.failure_threshold and self.state != CircuitState.OPEN:
                    logger.warning(f"[CircuitBreaker] Umbral de errores superado ({self.failures}). Cambiando a OPEN")
                    self.state = CircuitState.OPEN
                elif self.state == CircuitState.HALF_OPEN:
                    logger.warning("[CircuitBreaker] Error durante HALF_OPEN. Regresando a OPEN")
                    self.state = CircuitState.OPEN
            raise e
            
        async with self._lock:
            if self.state != CircuitState.CLOSED:
                logger.info("[CircuitBreaker] Conexión recuperada exitosamente. Cambiando a CLOSED")
                self.state = CircuitState.CLOSED
                self.failures = 0
                
        return result

# Instancias globales para aislar fallos por tipo de proveedor
llm_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
emb_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
