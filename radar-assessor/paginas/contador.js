/* Contador de visitas do gfrancis.com.br: sem cookies e sem dado pessoal.
   Conta a visita à página e os cliques em currículo, WhatsApp, LinkedIn e e-mail. */
(function () {
  if (/^(localhost|127\.)/.test(location.hostname)) return;
  function enviar(e) {
    try {
      var r = document.referrer ? new URL(document.referrer).hostname : "";
      if (r === location.hostname) r = "";
      var corpo = JSON.stringify({ e: e, p: location.pathname, r: r });
      if (navigator.sendBeacon) navigator.sendBeacon("/api/evento", new Blob([corpo], { type: "text/plain" }));
      else fetch("/api/evento", { method: "POST", body: corpo, keepalive: true });
    } catch (_) {}
  }
  enviar("visita");
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a, button[data-exemplo]");
    if (!a) return;
    var h = a.getAttribute("href") || "";
    if (h.indexOf("curriculo") >= 0) enviar("curriculo");
    else if (h.indexOf("wa.me") >= 0) enviar("whatsapp");
    else if (h.indexOf("linkedin.com") >= 0) enviar("linkedin");
    else if (h.indexOf("mailto:") === 0) enviar("email");
    else if (a.hasAttribute("data-exemplo")) enviar("ferramenta");
  }, true);
})();
