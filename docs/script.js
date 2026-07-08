// Landing page — Sistema de Caja Registradora Didáctica
// Todo vainilla, sin frameworks ni dependencias externas.

// ---------------------------------------------------------------- reloj
function ticReloj() {
  const el = document.getElementById("reloj-vivo");
  if (!el) return;
  const ahora = new Date();
  const f = (n) => String(n).padStart(2, "0");
  el.textContent =
    `${f(ahora.getDate())}/${f(ahora.getMonth() + 1)}/${ahora.getFullYear()}  ` +
    `${f(ahora.getHours())}:${f(ahora.getMinutes())}:${f(ahora.getSeconds())}`;
}
setInterval(ticReloj, 1000);
ticReloj();

// ---------------------------------------------------------------- reveal on scroll
const observador = new IntersectionObserver(
  (entradas) => {
    entradas.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("visible");
        observador.unobserve(e.target);
      }
    });
  },
  { threshold: 0.12 }
);
document.querySelectorAll(".reveal").forEach((el) => observador.observe(el));

// ---------------------------------------------------------------- recibo animado del hero
const RECIBO_DEMO = [
  ["Arroz Diana 500g", "4.500"],
  ["Azúcar Manuelita 1kg", "5.200"],
  ["Aceite Premier 1L", "14.000"],
];
function animarReciboHero() {
  const cont = document.getElementById("recibo-lineas");
  const totalEl = document.getElementById("recibo-total");
  if (!cont) return;
  cont.innerHTML = "";
  let total = 0;
  RECIBO_DEMO.forEach((item, i) => {
    const div = document.createElement("div");
    div.className = "linea";
    div.style.animationDelay = `${i * 0.45 + 0.3}s`;
    div.innerHTML = `<span class="desc">${item[0]}</span><span class="val">$${item[1]}</span>`;
    cont.appendChild(div);
    total += parseInt(item[1].replace(".", ""), 10);
  });
  setTimeout(() => {
    if (totalEl) totalEl.textContent = "$" + total.toLocaleString("es-CO");
  }, RECIBO_DEMO.length * 450 + 400);
}
animarReciboHero();
setInterval(animarReciboHero, 6000);

// ---------------------------------------------------------------- contadores animados
function animarContador(el) {
  const destino = parseFloat(el.dataset.contar);
  const decimales = el.dataset.contar.includes(".") ? 1 : 0;
  const duracion = 1200;
  const inicio = performance.now();
  function paso(ahora) {
    const t = Math.min(1, (ahora - inicio) / duracion);
    const valor = destino * (1 - Math.pow(1 - t, 3)); // ease-out cúbico
    el.textContent = valor.toFixed(decimales) + (el.dataset.sufijo || "");
    if (t < 1) requestAnimationFrame(paso);
  }
  requestAnimationFrame(paso);
}
const observadorContadores = new IntersectionObserver(
  (entradas) => {
    entradas.forEach((e) => {
      if (e.isIntersecting) {
        animarContador(e.target);
        observadorContadores.unobserve(e.target);
      }
    });
  },
  { threshold: 0.6 }
);
document.querySelectorAll("[data-contar]").forEach((el) => observadorContadores.observe(el));

// ---------------------------------------------------------------- demo interactiva de caja
const PRODUCTOS_DEMO = {
  "7701001": { nombre: "Arroz Diana 500g", precio: 4500 },
  "7701002": { nombre: "Azúcar Manuelita 1kg", precio: 5200 },
  "7701003": { nombre: "Aceite Premier 1L", precio: 14000 },
  "7701004": { nombre: "Leche Alquería 1L", precio: 4800 },
  "7701016": { nombre: "Gaseosa Coca-Cola 1.5L", precio: 6800 },
  "7701017": { nombre: "Agua Cristal 600ml", precio: 2000 },
};

(function iniciarDemo() {
  const form = document.getElementById("demo-form");
  if (!form) return;
  const entrada = document.getElementById("demo-codigo");
  const lista = document.getElementById("demo-lineas");
  const vacio = document.getElementById("demo-vacio");
  const errorEl = document.getElementById("demo-error");
  const totalEl = document.getElementById("demo-total");
  let total = 0;
  let items = 0;

  function formatoCOP(n) {
    return "$" + n.toLocaleString("es-CO");
  }

  function agregar(codigo, cantidad) {
    const producto = PRODUCTOS_DEMO[codigo];
    if (!producto) {
      errorEl.textContent = `El código «${codigo}» no existe en esta demo — pruebe uno de los chips de abajo.`;
      return;
    }
    errorEl.textContent = "";
    if (vacio) vacio.remove();
    const fila = document.createElement("div");
    fila.className = "fila";
    const subtotal = producto.precio * cantidad;
    fila.innerHTML = `<span class="n">${producto.nombre}${cantidad > 1 ? " ×" + cantidad : ""}</span>
                       <span class="c">${codigo}</span>
                       <span class="p">${formatoCOP(subtotal)}</span>`;
    lista.appendChild(fila);
    lista.scrollTop = lista.scrollHeight;
    total += subtotal;
    items += cantidad;
    totalEl.textContent = formatoCOP(total);
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    let texto = entrada.value.trim();
    if (!texto) return;
    let cantidad = 1;
    const mult = texto.match(/^(\d+)\*(.+)$/);
    if (mult) {
      cantidad = Math.max(1, parseInt(mult[1], 10));
      texto = mult[2];
    }
    agregar(texto, cantidad);
    entrada.value = "";
    entrada.focus();
  });

  document.querySelectorAll(".chip-codigo").forEach((chip) => {
    chip.addEventListener("click", () => {
      entrada.value = chip.dataset.codigo;
      form.requestSubmit();
    });
  });
})();

// ---------------------------------------------------------------- año en el footer
const elAnio = document.getElementById("anio-actual");
if (elAnio) elAnio.textContent = new Date().getFullYear();
