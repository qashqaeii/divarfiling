/**
 * پخش‌کننده ویدیوی آموزشی نصب ربات — overlay پلی و مخفی‌سازی پس از شروع
 */
(function () {
    function initPlayer(root) {
        var frame = root.querySelector('.mk-vid-frame');
        var video = root.querySelector('.mk-vid-el');
        var playBtn = root.querySelector('[data-mk-vid-play]');
        if (!frame || !video) return;

        function setPlaying(playing) {
            frame.classList.toggle('is-playing', playing);
        }

        function setEnded(ended) {
            frame.classList.toggle('is-ended', ended);
            if (ended) frame.classList.remove('is-playing');
        }

        if (playBtn) {
            playBtn.addEventListener('click', function () {
                video.play().catch(function () {});
            });
        }

        video.addEventListener('play', function () {
            setPlaying(true);
            setEnded(false);
        });

        video.addEventListener('pause', function () {
            if (!video.ended) setPlaying(false);
        });

        video.addEventListener('ended', function () {
            setPlaying(false);
            setEnded(true);
        });
    }

    document.querySelectorAll('[data-mk-vid-player]').forEach(initPlayer);
})();
