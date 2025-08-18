window.addEventListener('DOMContentLoaded', () => {
  const detectores = document.querySelectorAll('.bloque-detector');

  detectores.forEach(detector => {
    const boton = detector.querySelector('.btn-aparece');

    detector.addEventListener('mouseenter', () => {
      boton.classList.add('mostrar');
    });

    detector.addEventListener('mouseleave', () => {
      boton.classList.remove('mostrar');
    });
  });
});
