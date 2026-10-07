/**
 * پخش‌کننده ویدیوی آموزشی — overlay پلی سفارشی؛ controls مرورگر پس از شروع پخش
 */
(function () {
    function initPlayer(root) {
        var frame = root.querySelector('.mk-vid-frame');
        var video = root.querySelector('.mk-vid-el');
        var playBtn = root.querySelector('[data-mk-vid-play]');
        if (!frame || !video) return;

        video.removeAttribute('controls');

        function setPlaying(playing) {
            frame.classList.toggle('is-playing', playing);
        }

        function setEnded(ended) {
            frame.classList.toggle('is-ended', ended);
            if (ended) frame.classList.remove('is-playing');
        }

        function enableNativeControls() {
            if (!video.hasAttribute('controls')) {
                video.setAttribute('controls', '');
            }
        }

        function startPlayback() {
            enableNativeControls();
            video.play().catch(function () {});
        }

        if (playBtn) {
            playBtn.addEventListener('click', startPlayback);
        }

        video.addEventListener('play', function () {
            enableNativeControls();
            setPlaying(true);
            setEnded(false);
        });

        video.addEventListener('pause', function () {
            if (video.ended) return;
            if (video.currentTime > 0) {
                setPlaying(true);
            } else {
                setPlaying(false);
            }
        });

        video.addEventListener('ended', function () {
            video.removeAttribute('controls');
            setPlaying(false);
            setEnded(true);
        });
    }

    document.querySelectorAll('[data-mk-vid-player]').forEach(initPlayer);
})();
