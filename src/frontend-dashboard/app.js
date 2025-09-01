// Location: `/src/frontend-dashboard/app.js`

class KubeEstateHubApp {
  constructor() {
    this.apiBaseUrl = window.location.hostname.includes("localhost")
      ? "http://localhost:8080/api/v1"
      : "/api/v1";

    this.currentPage = 1;
    this.itemsPerPage = 20;
    this.currentFilters = {};
    this.charts = {};

    this.init();
  }

  async init() {
    this.setupEventListeners();
    this.checkApiConnection();
    await this.loadDashboardData();
    this.hideLoading();
  }

  setupEventListeners() {
    // Navigation
    document.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const section = link.dataset.section;
        this.showSection(section);
        this.updateNavigation(link);
      });
    });

    // Theme toggle
    document.getElementById("theme-toggle").addEventListener("click", () => {
      this.toggleTheme();
    });

    // Add listing modal
    document.getElementById("add-listing-btn").addEventListener("click", () => {
      this.showAddListingModal();
    });

    document.getElementById("cancel-listing").addEventListener("click", () => {
      this.hideAddListingModal();
    });

    document.querySelector(".modal-close").addEventListener("click", () => {
      this.hideAddListingModal();
    });

    // Add listing form
    document
      .getElementById("add-listing-form")
      .addEventListener("submit", (e) => {
        e.preventDefault();
        this.handleAddListing();
      });

    // Filters
    document.getElementById("apply-filters").addEventListener("click", () => {
      this.applyFilters();
    });

    document.getElementById("clear-filters").addEventListener("click", () => {
      this.clearFilters();
    });

    // Toast close buttons
    document.querySelectorAll(".toast-close").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.target.closest(".toast").classList.remove("show");
      });
    });

    // Settings
    document
      .getElementById("items-per-page")
      .addEventListener("change", (e) => {
        this.itemsPerPage = parseInt(e.target.value);
        localStorage.setItem("itemsPerPage", this.itemsPerPage);
      });

    document
      .getElementById("dark-mode-setting")
      .addEventListener("change", (e) => {
        if (e.target.checked) {
          this.setTheme("dark");
        } else {
          this.setTheme("light");
        }
      });

    // Load settings
    this.loadSettings();
  }

  loadSettings() {
    // Load items per page
    const savedItemsPerPage = localStorage.getItem("itemsPerPage");
    if (savedItemsPerPage) {
      this.itemsPerPage = parseInt(savedItemsPerPage);
      document.getElementById("items-per-page").value = this.itemsPerPage;
    }

    // Load theme
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      this.setTheme(savedTheme);
      document.getElementById("dark-mode-setting").checked =
        savedTheme === "dark";
    }

    // Set API endpoint
    document.getElementById("api-endpoint").value = this.apiBaseUrl;
  }

  showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll(".section").forEach((section) => {
      section.classList.remove("active");
    });

    // Show target section
    document.getElementById(sectionId).classList.add("active");

    // Load section-specific data
    switch (sectionId) {
      case "listings":
        this.loadListings();
        break;
      case "analytics":
        this.loadAnalytics();
        break;
      case "settings":
        this.checkApiConnection();
        break;
    }
  }

  updateNavigation(activeLink) {
    document.querySelectorAll(".nav-link").forEach((link) => {
      link.classList.remove("active");
    });
    activeLink.classList.add("active");
  }

  async checkApiConnection() {
    const statusEl = document.getElementById("api-status");

    try {
      const response = await fetch(
        `${this.apiBaseUrl.replace("/api/v1", "")}/health`
      );
      if (response.ok) {
        statusEl.innerHTML =
          '<i class="fas fa-circle" style="color: #22c55e;"></i> Connected';
        statusEl.className = "status-indicator connected";
      } else {
        throw new Error("API not responding");
      }
    } catch (error) {
      statusEl.innerHTML =
        '<i class="fas fa-circle" style="color: #ef4444;"></i> Disconnected';
      statusEl.className = "status-indicator disconnected";
    }
  }

  async loadDashboardData() {
    try {
      // Load listings for stats
      const response = await fetch(`${this.apiBaseUrl}/listings?per_page=1`);
      if (!response.ok) throw new Error("Failed to load listings");

      const data = await response.json();

      // Update stats
      document.getElementById("total-listings").textContent =
        data.pagination.total.toLocaleString();

      // Load sample data for other stats (in real app, these would be separate endpoints)
      document.getElementById("avg-price").textContent = "$485,000";
      document.getElementById("avg-days").textContent = "35 days";
      document.getElementById("market-trend").textContent = "↗ Up 5.2%";

      // Load charts
      this.initCharts();
    } catch (error) {
      console.error("Error loading dashboard data:", error);
      this.showToast("error", "Failed to load dashboard data");
    }
  }

  initCharts() {
    // Price Trend Chart
    const priceTrendCtx = document
      .getElementById("price-trend-chart")
      .getContext("2d");
    this.charts.priceTrend = new Chart(priceTrendCtx, {
      type: "line",
      data: {
        labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        datasets: [
          {
            label: "Average Price",
            data: [450000, 465000, 470000, 485000, 490000, 485000],
            borderColor: "#3b82f6",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: {
              callback: function (value) {
                return "$" + value / 1000 + "K";
              },
            },
          },
        },
      },
    });

    // Property Type Chart
    const propertyTypeCtx = document
      .getElementById("property-type-chart")
      .getContext("2d");
    this.charts.propertyType = new Chart(propertyTypeCtx, {
      type: "doughnut",
      data: {
        labels: ["Residential", "Commercial", "Industrial", "Land"],
        datasets: [
          {
            data: [65, 20, 10, 5],
            backgroundColor: ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });
  }

  async loadListings() {
    try {
      const params = new URLSearchParams({
        page: this.currentPage,
        per_page: this.itemsPerPage,
        ...this.currentFilters,
      });

      const response = await fetch(`${this.apiBaseUrl}/listings?${params}`);
      if (!response.ok) throw new Error("Failed to load listings");

      const data = await response.json();
      this.renderListings(data.listings);
      this.renderPagination(data.pagination);
    } catch (error) {
      console.error("Error loading listings:", error);
      this.showToast("error", "Failed to load listings");
    }
  }

  renderListings(listings) {
    const grid = document.getElementById("listings-grid");

    if (listings.length === 0) {
      grid.innerHTML = '<div class="no-results">No listings found</div>';
      return;
    }

    grid.innerHTML = listings
      .map(
        (listing) => `
            <div class="listing-card">
                <div class="listing-image">
                    <img src="${listing.image_url || "/placeholder-home.jpg"}" 
                         alt="${listing.title}" 
                         onerror="this.src='/placeholder-home.jpg'">
                    <div class="listing-status ${listing.status}">${
          listing.status
        }</div>
                </div>
                <div class="listing-content">
                    <h3 class="listing-title">${listing.title}</h3>
                    <p class="listing-address">
                        <i class="fas fa-map-marker-alt"></i>
                        ${listing.address}, ${listing.city}, ${listing.state}
                    </p>
                    <div class="listing-details">
                        <span class="detail-item">
                            <i class="fas fa-bed"></i> ${
                              listing.bedrooms || "N/A"
                            }
                        </span>
                        <span class="detail-item">
                            <i class="fas fa-bath"></i> ${
                              listing.bathrooms || "N/A"
                            }
                        </span>
                        <span class="detail-item">
                            <i class="fas fa-ruler-combined"></i> ${
                              listing.square_feet
                                ? listing.square_feet.toLocaleString() +
                                  " sq ft"
                                : "N/A"
                            }
                        </span>
                    </div>
                    <div class="listing-price">$${listing.price.toLocaleString()}</div>
                    <div class="listing-meta">
                        <span class="listing-type">${
                          listing.property_type
                        }</span>
                        <span class="listing-date">Listed ${new Date(
                          listing.listing_date
                        ).toLocaleDateString()}</span>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  renderPagination(pagination) {
    const container = document.getElementById("pagination");
    const { page, pages, total } = pagination;

    if (pages <= 1) {
      container.innerHTML = "";
      return;
    }

    let html = `<div class="pagination-info">Showing page ${page} of ${pages} (${total} total)</div>`;
    html += '<div class="pagination-buttons">';

    // Previous button
    if (page > 1) {
      html += `<button class="pagination-btn" data-page="${
        page - 1
      }">Previous</button>`;
    }

    // Page numbers
    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(pages, page + 2);

    if (startPage > 1) {
      html += `<button class="pagination-btn" data-page="1">1</button>`;
      if (startPage > 2) {
        html += '<span class="pagination-ellipsis">...</span>';
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      html += `<button class="pagination-btn ${
        i === page ? "active" : ""
      }" data-page="${i}">${i}</button>`;
    }

    if (endPage < pages) {
      if (endPage < pages - 1) {
        html += '<span class="pagination-ellipsis">...</span>';
      }
      html += `<button class="pagination-btn" data-page="${pages}">${pages}</button>`;
    }

    // Next button
    if (page < pages) {
      html += `<button class="pagination-btn" data-page="${
        page + 1
      }">Next</button>`;
    }

    html += "</div>";
    container.innerHTML = html;

    // Add event listeners
    container.querySelectorAll(".pagination-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.currentPage = parseInt(btn.dataset.page);
        this.loadListings();
      });
    });
  }

  applyFilters() {
    this.currentFilters = {};

    const city = document.getElementById("city-filter").value;
    if (city) this.currentFilters.city = city;

    const propertyType = document.getElementById("property-type-filter").value;
    if (propertyType) this.currentFilters.property_type = propertyType;

    const minPrice = document.getElementById("min-price").value;
    if (minPrice) this.currentFilters.min_price = minPrice;

    const maxPrice = document.getElementById("max-price").value;
    if (maxPrice) this.currentFilters.max_price = maxPrice;

    this.currentPage = 1;
    this.loadListings();
  }

  clearFilters() {
    document.getElementById("city-filter").value = "";
    document.getElementById("property-type-filter").value = "";
    document.getElementById("min-price").value = "";
    document.getElementById("max-price").value = "";

    this.currentFilters = {};
    this.currentPage = 1;
    this.loadListings();
  }

  async loadAnalytics() {
    try {
      // In a real app, this would call analytics endpoints
      this.initMarketTrendsChart();
      this.loadTopCities();
      this.loadMarketMetrics();
    } catch (error) {
      console.error("Error loading analytics:", error);
      this.showToast("error", "Failed to load analytics");
    }
  }

  initMarketTrendsChart() {
    const ctx = document.getElementById("market-trends-chart").getContext("2d");
    if (this.charts.marketTrends) {
      this.charts.marketTrends.destroy();
    }

    this.charts.marketTrends = new Chart(ctx, {
      type: "line",
      data: {
        labels: [
          "Q1 2023",
          "Q2 2023",
          "Q3 2023",
          "Q4 2023",
          "Q1 2024",
          "Q2 2024",
        ],
        datasets: [
          {
            label: "Austin",
            data: [425000, 445000, 465000, 485000, 495000, 485000],
            borderColor: "#3b82f6",
            tension: 0.4,
          },
          {
            label: "Houston",
            data: [385000, 395000, 405000, 415000, 420000, 425000],
            borderColor: "#10b981",
            tension: 0.4,
          },
          {
            label: "Dallas",
            data: [395000, 410000, 425000, 440000, 445000, 450000],
            borderColor: "#f59e0b",
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: false,
            ticks: {
              callback: function (value) {
                return "$" + value / 1000 + "K";
              },
            },
          },
        },
      },
    });
  }

  loadTopCities() {
    const container = document.getElementById("top-cities-list");
    const cities = [
      { name: "Austin", sales: 1250, growth: "+5.2%" },
      { name: "Houston", sales: 980, growth: "+2.8%" },
      { name: "Dallas", sales: 875, growth: "+4.1%" },
      { name: "San Antonio", sales: 650, growth: "+1.9%" },
    ];

    container.innerHTML = cities
      .map(
        (city) => `
            <div class="city-item">
                <div class="city-info">
                    <span class="city-name">${city.name}</span>
                    <span class="city-sales">${city.sales} sales</span>
                </div>
                <span class="city-growth ${
                  city.growth.includes("+") ? "positive" : "negative"
                }">${city.growth}</span>
            </div>
        `
      )
      .join("");
  }

  loadMarketMetrics() {
    document.getElementById("sales-volume").textContent = "3,755 units";
    document.getElementById("price-growth").textContent = "+3.8% YoY";
    document.getElementById("inventory-levels").textContent = "2.3 months";
  }

  showAddListingModal() {
    document.getElementById("add-listing-modal").classList.add("show");
  }

  hideAddListingModal() {
    document.getElementById("add-listing-modal").classList.remove("show");
    document.getElementById("add-listing-form").reset();
  }

  async handleAddListing() {
    const formData = {
      mls_number: document.getElementById("mls-number").value,
      title: document.getElementById("listing-title").value,
      price: parseInt(document.getElementById("listing-price").value),
      property_type: document.getElementById("listing-type").value,
      address: "123 Example St",
      city: "Austin",
      state: "TX",
      zip_code: "78701",
    };

    try {
      const response = await fetch(`${this.apiBaseUrl}/listings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to create listing");
      }

      this.hideAddListingModal();
      this.showToast("success", "Listing created successfully");
      this.loadListings();
    } catch (error) {
      console.error("Error creating listing:", error);
      this.showToast("error", error.message);
    }
  }

  toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    this.setTheme(newTheme);
  }

  setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);

    const themeToggle = document.getElementById("theme-toggle");
    const icon = themeToggle.querySelector("i");

    if (theme === "dark") {
      icon.className = "fas fa-sun";
    } else {
      icon.className = "fas fa-moon";
    }
  }

  showToast(type, message) {
    const toast = document.getElementById(`${type}-toast`);
    const messageEl = document.getElementById(`${type}-message`);

    messageEl.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
      toast.classList.remove("show");
    }, 5000);
  }

  hideLoading() {
    document.getElementById("loading-spinner").style.display = "none";
  }

  formatCurrency(amount) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(amount);
  }

  formatNumber(number) {
    return new Intl.NumberFormat("en-US").format(number);
  }
}

// Initialize app when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  new KubeEstateHubApp();
});

// Service Worker registration for PWA functionality
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        console.log("SW registered: ", registration);
      })
      .catch((registrationError) => {
        console.log("SW registration failed: ", registrationError);
      });
  });
}
