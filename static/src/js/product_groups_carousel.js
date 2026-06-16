document.addEventListener('DOMContentLoaded', () => {

    const track = document.querySelector(".carousel-track")
    const wrapper = document.querySelector(".carousel-track-wrapper")
    const prevBtn = document.querySelector(".prev-btn")
    const nextBtn = document.querySelector(".next-btn")
    const thumb = document.querySelector(".carousel-scrollbar-thumb")
    const scrollTrack = document.querySelector(".carousel-scrollbar-track")

    if (!track || !wrapper || !prevBtn || !nextBtn) {

        console.log("error 1")
        return

    } 

    let currentTranslate = 0
    const gap = 35

    function updateCarousel() {

        const maxTranslate = track.scrollWidth - wrapper.clientWidth

        if (currentTranslate < 0) currentTranslate = 0;
        if (currentTranslate > maxTranslate) currentTranslate = maxTranslate;

        track.style.transform = `translateX(-${currentTranslate}px)`

        if (maxTranslate > 0) {

            const progress = currentTranslate / maxTranslate

            const maxThumbTranslate = scrollTrack.clientWidth - thumb.clientWidth - 20
            const thumbTranslate = progress * maxThumbTranslate

            thumb.style.transform = `translateX(${thumbTranslate}px)`

        }

    }

    nextBtn.addEventListener('click', () => {

        const card = document.querySelector(".carousel-card")

        if (!card) {

            console.log("error 2")
            return

        }

        const step = card.clientWidth + gap
        currentTranslate += step
        updateCarousel()

    })

    prevBtn.addEventListener('click', () => {

        const card = document.querySelector(".carousel-card")

        
        if (!card) {

            console.log("error 2")
            return

        }

        const step = card.clientWidth + gap
        currentTranslate -= step
        updateCarousel()

    })

    window.addEventListener('resize', () => {
        // Пересчитываем положение, чтобы верстка не ломалась
        updateCarousel();
    });

})