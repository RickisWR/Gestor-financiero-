document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    // Detectar si es móvil (pantalla menor a 768px)
    const isMobile = window.innerWidth <= 768;

    const saveMenuState = (isCollapsed) => {
        localStorage.setItem('menuCollapsed', isCollapsed);
    };

    const loadMenuState = () => {
        return localStorage.getItem('menuCollapsed') === 'true';
    };

    // --- LÓGICA DE INICIO CORREGIDA ---
    if (isMobile) {
        // En móvil, SIEMPRE empezar colapsado (oculto) para no tapar la pantalla
        sidebar.classList.add('collapsed');
    } else {
        // En escritorio, respetar la preferencia del usuario
        if (loadMenuState()) {
            sidebar.classList.add('collapsed');
        }
    }

    if(menuToggle) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            
            // Solo guardamos el estado si NO es móvil
            if (!isMobile) {
                saveMenuState(sidebar.classList.contains('collapsed'));
            }
        });
    }

    // --- CERRAR AL HACER CLIC EN UN ENLACE (SOLO MÓVIL) ---
    // Esto mejora la experiencia: si tocas una opción, el menú se quita solo.
    if (isMobile) {
        const links = sidebar.querySelectorAll('a');
        links.forEach(link => {
            link.addEventListener('click', () => {
                sidebar.classList.add('collapsed');
            });
        });
    }
});

// --- LÓGICA DEL MENÚ DE USUARIO (LOGO) - NUEVO ---
function toggleUserMenu() {
    const dropdown = document.getElementById("user-dropdown");
    if (dropdown) {
        dropdown.classList.toggle("mostrar");
    }
}

// Cerrar el menú si se hace click fuera
window.addEventListener('click', function(e) {
    if (!e.target.closest('.user-menu-container')) {
        const dropdown = document.getElementById("user-dropdown");
        if (dropdown && dropdown.classList.contains('mostrar')) {
            dropdown.classList.remove('mostrar');
        }
    }
});