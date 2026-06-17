import '../css/main.scss'; 
import '../css/null.scss';
import '../css/header.scss'
import '../css/product_groups.scss'
import '../css/manufacturers.scss'
import '../css/clients.scss'
import '../css/footer.scss'
import 'vite/modulepreload-polyfill';

document.addEventListener('DOMContentLoaded', () => {

    const slides = document.querySelectorAll('.hero-slider .slide')
    const sliderSection = document.querySelector('.hero-slider')

    if (slides.length <= 1) return;

    let currentSlide = 0
    const slideInterval = 5000
    let autoSlideTimer

    function goToSlide(index) {

        slides[currentSlide].classList.remove('active')

        currentSlide = index

        slides[currentSlide].classList.add('active')

        const wrapper = document.querySelector(".slider-wrapper")
        if (wrapper) {

            wrapper.style.transform = `translateX(-${index * 100}%)`;

        }

    }

    function nextSlide() {

        let nextIndex = (currentSlide + 1) % slides.length
        goToSlide(nextIndex)

    }

    function startTimer() {

        autoSlideTimer = setInterval(nextSlide, slideInterval)

    }

    startTimer()

})