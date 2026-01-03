// ================= SEARCH ===================
const searchIcon = document.getElementById('openSearch');
const closeIcon = document.getElementById('closeSearch');
const searchBox = document.getElementById('searchBox');
const input = document.querySelector('.search-input');

searchIcon.addEventListener('click', () => {
  searchBox.classList.add('active');
  searchIcon.style.display = 'none';
  closeIcon.style.display = 'inline';
  input.focus();
});

closeIcon.addEventListener('click', () => {
  searchBox.classList.remove('active');
  closeIcon.style.display = 'none';
  searchIcon.style.display = 'inline';
  input.value = '';
});

// ================= CART ===================

// AJAX Add to Cart
function addToCartAjax(productId) {
  fetch("/add_to_cart", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "product_id=" + productId
  })
  .then(res => res.json())
  .then(data => {

      console.log(data); // cek response di console

      // ⬇ kalau belum login
      if (data.error === "not_logged_in") {
          window.location.href = "/login";
          return;
      }

      // kalau sudah ada di cart
      if (data.error === "exists") {
          showToast("Produk sudah ada di cart");
          return;
      }

      // kalau berhasil
      if (data.success === true) {
          showToast("Berhasil ditambahkan ke cart!");

          setTimeout(() => {
              updateCartSidebar();
          }, 200);
      }
  });
}





// Update sidebar
function updateCartSidebar() {
    fetch("/get_cart_items")
        .then(res => res.json())
        .then(items => {
            const cartArea = document.getElementById("cartArea");
            const emptyBox = document.getElementById("emptyCartBox");

            cartArea.innerHTML = "";

            if (items.length === 0) {
                emptyBox.style.display = "block";
                cartArea.style.display = "none";
                return;
            }

            emptyBox.style.display = "none";
            cartArea.style.display = "block";

           
           
           
            items.forEach(item => {
    cartArea.innerHTML += `
        <div class="d-flex justify-content-between align-items-center border-bottom py-3">
            <div>
                <strong>${item.name}</strong><br>
                <small>Qty: ${item.quantity}</small><br>
                <small>Rp ${item.price * item.quantity}</small>

                <div class="mt-2">
                    <button class="btn btn-sm btn-danger"
                        onclick="deleteCartItem(${item.product_id})">
                        Delete
                    </button>

                    <button class="btn btn-sm btn-dark"
                        onclick="buyNow(${item.product_id})">
                        Buy Now
                    </button>
                </div>
            </div>

            <img src="/static/images/${item.image}" width="60" class="rounded">
        </div>
    `;
});

        });
}


// Update otomatis saat sidebar dibuka
document.getElementById("cartSidebar")
    .addEventListener("shown.bs.offcanvas", updateCartSidebar);

// ================= BUY & REMOVE ===================
function removeFromCart(id) {
    fetch(`/remove/${id}`).then(() => updateCartSidebar());
}

function buyNow(productId) {
    console.log("BUY NOW ID:", productId); // Debug
    window.location.href = `/checkout/${productId}`;
}


// ================= SCROLL EFFECT ===================
const faders = document.querySelectorAll('.fade-in');
const appearOnScroll = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('show');
        obs.unobserve(entry.target);
    });
}, { threshold: 0.2 });

faders.forEach(el => appearOnScroll.observe(el));

function deleteCartItem(productId) {
    fetch(`/delete_cart_item/${productId}`, {
        method: "POST"
    })
    .then(res => res.json())
    .then(() => updateCartSidebar());
}

function scrollToProducts() {
    const target = document.getElementById("productSection");
    if (!target) return;

    const top = target.getBoundingClientRect().top + window.pageYOffset;

    smoothScrollTo(top, 900); // 900ms = smooth banget
}

function smoothScrollTo(targetY, duration = 800) {
    const startY = window.pageYOffset;
    const distance = targetY - startY;
    let startTime = null;

    function easing(t) {
        // Ease-out cubic (smooth lembut)
        return 1 - Math.pow(1 - t, 3);
    }

    function animation(currentTime) {
        if (!startTime) startTime = currentTime;

        const timeProgress = Math.min((currentTime - startTime) / duration, 1);
        const smoothStep = easing(timeProgress);

        window.scrollTo(0, startY + distance * smoothStep);

        if (timeProgress < 1) {
            requestAnimationFrame(animation);
        }
    }

    requestAnimationFrame(animation);
}

function showToast(message) {
    const toast = document.getElementById("toast");
    toast.innerText = message;

    toast.style.opacity = "1";

    setTimeout(() => {
        toast.style.opacity = "0";
    }, 2000);
}


document.getElementById("subscribeForm").addEventListener("submit", function(e) {
    e.preventDefault();

    const formData = new FormData(this);

    fetch("/subscribe", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            document.getElementById("subscribeMsg").style.display = "block";

            // kosongkan input
            this.reset();

            // sembunyikan setelah 3 detik
            setTimeout(() => {
                document.getElementById("subscribeMsg").style.display = "none";
            }, 3000);
        }
    });
});


    // Chart initialization should be in the HTML template, not here
    // Move this code block to your HTML template file where {{ labels | tojson }} can be properly rendered

