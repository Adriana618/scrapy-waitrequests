# src/scrapy_waitrequests/wait_request.py

import scrapy
from twisted.internet import reactor
from twisted.internet.defer import Deferred

class WaitRequest(scrapy.Request):
    def __init__(
        self,
        url,
        method='GET',
        callback=None,
        errback=None,
        wait_time=2.0,
        max_tries=3,
        check_condition=None,
        tries=1,
        *args,
        **kwargs
    ):
        """
        :param url: URL del request.
        :param method: Método HTTP (GET, POST, ...).
        :param callback: Callback final a ejecutar cuando la condición se cumpla
                         o cuando se acaben los reintentos.
        :param errback: errback final a ejecutar en caso de error (o reintento fallido).
        :param wait_time: Número de segundos que esperaremos entre reintentos.
        :param max_tries: Límite máximo de reintentos antes de rendirnos.
        :param check_condition: Función que recibe 'response' y retorna True/False
                                indicando si ya está "OK" la respuesta.
        :param tries: Contador interno de cuántos intentos llevamos.
        :param args, kwargs: Se pasan a la clase base Request (headers, formdata, meta, etc.).
        """
        self._wait_time = wait_time
        self._max_tries = max_tries
        self._check_condition = check_condition
        self._tries = tries

        # Guardamos el callback y errback que definió el usuario.
        self._final_callback = callback
        self._final_errback = errback

        # Guardamos también el método original, para reproducirlo en los reintentos.
        self._original_method = method

        # Guardamos args y kwargs en crudo para usarlos al recrear la request.
        self._init_args = args
        self._init_kwargs = kwargs

        # Forzamos que el callback/errback "externo" sea el nuestro interno.
        super().__init__(
            url=url,
            method=method,
            callback=self._wait_callback,
            errback=self._wait_errback,
            *args,
            **kwargs
        )

    def _wait_callback(self, response):
        """
        Callback interno que decide si la condición se cumplió.
        Si NO, programa un reintento usando callLater.
        Si SÍ o si no hay que verificar nada, pasa al callback real.
        """
        if self._check_condition and not self._check_condition(response):
            # No se cumple la condición (por ejemplo, captcha aun no resuelto)
            if self._tries < self._max_tries:
                # Programamos reintento asíncrono
                d = Deferred()
                reactor.callLater(self._wait_time, lambda: d.callback(self._retry()))
                return d
            else:
                # Se alcanzó el número máximo de intentos sin éxito
                # Puedes decidir si llamas al callback final con la respuesta (por ejemplo,
                # para que haga un "fall back") o devuelves None. Aquí lo llamamos:
                if self._final_callback:
                    return self._final_callback(response)
                else:
                    return None
        else:
            # Si la condición se cumple (o no hay condición),
            # entonces llamamos al callback final.
            if self._final_callback:
                return self._final_callback(response)
            else:
                return None

    def _wait_errback(self, failure):
        """
        errback interno que decide si reintentar o no ante un error.
        'failure' es un objeto Twisted que encapsula el error/exception.
        """
        # Aquí tienes dos opciones:
        #  1) Reintentar (igual que si "no se cumple la condición").
        #  2) Llamar directamente a _final_errback si existe y abortar reintentos.
        #  3) O combinar la lógica: reintentar N veces y luego si sigue fallando, abortar.

        if self._tries < self._max_tries:
            d = Deferred()
            reactor.callLater(self._wait_time, lambda: d.callback(self._retry()))
            return d
        else:
            # Si ya se superó max_tries, invocamos al errback final (si está definido).
            if self._final_errback:
                return self._final_errback(failure)
            else:
                # si no hay errback final, retornamos el failure (propaga el error a Scrapy).
                return failure

    def _retry(self):
        """
        Crea una nueva instancia de WaitRequest con tries+1, usando
        los mismos parámetros (url, method, etc.) y la misma meta, headers...
        """
        new_req = WaitRequest(
            url=self.url,
            method=self._original_method,
            callback=self._final_callback,
            errback=self._final_errback,
            wait_time=self._wait_time,
            max_tries=self._max_tries,
            check_condition=self._check_condition,
            tries=self._tries + 1,
            *self._init_args,
            **self._init_kwargs
        )
        new_req.dont_filter = True  # Para que Scrapy no lo descarte como 'visitado'.
        
        # Si necesitas mantener la meta, la copiamos
        # Ojo: decide si quieres copy() o no.
        new_req.meta = self.meta  
        
        return new_req