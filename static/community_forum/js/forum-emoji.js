/**
 * Emoji picker تالار گفتگو — بدون CDN، داده Unicode محلی، popover / bottom sheet
 */
(function (global) {
  'use strict';

  var RECENT_KEY = 'cf_emoji_recent';
  var RECENT_MAX = 24;

  var CATEGORIES = [
    {
      id: 'recent',
      label: 'اخیر',
      items: [],
    },
    {
      id: 'smileys',
      label: 'احساسات',
      items: [
        { e: '😀', k: 'smile grin happy' }, { e: '😃', k: 'smile' }, { e: '😄', k: 'joy' },
        { e: '😁', k: 'beaming' }, { e: '😆', k: 'laugh' }, { e: '😅', k: 'sweat smile' },
        { e: '🤣', k: 'rofl' }, { e: '😂', k: 'joy tears' }, { e: '🙂', k: 'slight smile' },
        { e: '🙃', k: 'upside down' }, { e: '😉', k: 'wink' }, { e: '😊', k: 'blush' },
        { e: '😇', k: 'angel' }, { e: '🥰', k: 'love hearts' }, { e: '😍', k: 'heart eyes' },
        { e: '🤩', k: 'star eyes' }, { e: '😘', k: 'kiss' }, { e: '😗', k: 'kiss' },
        { e: '😚', k: 'kiss closed' }, { e: '😙', k: 'kiss smile' }, { e: '🥲', k: 'tear smile' },
        { e: '😋', k: 'yum' }, { e: '😛', k: 'tongue' }, { e: '😜', k: 'wink tongue' },
        { e: '🤪', k: 'zany' }, { e: '😝', k: 'squint tongue' }, { e: '🤑', k: 'money' },
        { e: '🤗', k: 'hug' }, { e: '🤭', k: 'hand mouth' }, { e: '🤫', k: 'shush' },
        { e: '🤔', k: 'think' }, { e: '🤐', k: 'zipper' }, { e: '🤨', k: 'raised brow' },
        { e: '😐', k: 'neutral' }, { e: '😑', k: 'expressionless' }, { e: '😶', k: 'no mouth' },
        { e: '😏', k: 'smirk' }, { e: '😒', k: 'unamused' }, { e: '🙄', k: 'roll eyes' },
        { e: '😬', k: 'grimace' }, { e: '😮‍💨', k: 'sigh' }, { e: '🤥', k: 'lying' },
        { e: '😌', k: 'relieved' }, { e: '😔', k: 'pensive' }, { e: '😪', k: 'sleepy' },
        { e: '🤤', k: 'drool' }, { e: '😴', k: 'sleep' }, { e: '😷', k: 'mask' },
        { e: '🤒', k: 'sick' }, { e: '🤕', k: 'hurt' }, { e: '🤢', k: 'nauseated' },
        { e: '🤮', k: 'vomit' }, { e: '🤧', k: 'sneeze' }, { e: '🥵', k: 'hot' },
        { e: '🥶', k: 'cold' }, { e: '🥴', k: 'woozy' }, { e: '😵', k: 'dizzy' },
        { e: '🤯', k: 'exploding head' }, { e: '🤠', k: 'cowboy' }, { e: '🥳', k: 'party' },
        { e: '😎', k: 'cool sunglasses' }, { e: '🤓', k: 'nerd' }, { e: '🧐', k: 'monocle' },
        { e: '😕', k: 'confused' }, { e: '😟', k: 'worried' }, { e: '🙁', k: 'frown' },
        { e: '☹️', k: 'frown' }, { e: '😮', k: 'open mouth' }, { e: '😯', k: 'hushed' },
        { e: '😲', k: 'astonished' }, { e: '😳', k: 'flushed' }, { e: '🥺', k: 'pleading' },
        { e: '😦', k: 'frown open' }, { e: '😧', k: 'anguished' }, { e: '😨', k: 'fearful' },
        { e: '😰', k: 'anxious sweat' }, { e: '😥', k: 'sad relieved' }, { e: '😢', k: 'cry' },
        { e: '😭', k: 'sob' }, { e: '😱', k: 'scream fear' }, { e: '😖', k: 'confounded' },
        { e: '😣', k: 'persevere' }, { e: '😞', k: 'disappointed' }, { e: '😓', k: 'downcast sweat' },
        { e: '😩', k: 'weary' }, { e: '😫', k: 'tired' }, { e: '🥱', k: 'yawn' },
        { e: '😤', k: 'triumph' }, { e: '😡', k: 'angry' }, { e: '😠', k: 'mad' },
        { e: '🤬', k: 'cursing' }, { e: '😈', k: 'smiling horns' }, { e: '👿', k: 'angry imp' },
        { e: '💀', k: 'skull' }, { e: '☠️', k: 'skull crossbones' }, { e: '💩', k: 'poop' },
        { e: '🤡', k: 'clown' }, { e: '👹', k: 'ogre' }, { e: '👺', k: 'goblin' },
        { e: '👻', k: 'ghost' }, { e: '👽', k: 'alien' }, { e: '🤖', k: 'robot' },
      ],
    },
    {
      id: 'people',
      label: 'افراد',
      items: [
        { e: '👋', k: 'wave hand' }, { e: '🤚', k: 'raised back hand' }, { e: '🖐️', k: 'hand fingers' },
        { e: '✋', k: 'raised hand' }, { e: '🖖', k: 'vulcan' }, { e: '👌', k: 'ok' },
        { e: '🤌', k: 'pinched fingers' }, { e: '🤏', k: 'pinch' }, { e: '✌️', k: 'victory peace' },
        { e: '🤞', k: 'crossed fingers' }, { e: '🤟', k: 'love you' }, { e: '🤘', k: 'rock horns' },
        { e: '🤙', k: 'call me' }, { e: '👈', k: 'point left' }, { e: '👉', k: 'point right' },
        { e: '👆', k: 'point up' }, { e: '👇', k: 'point down' }, { e: '☝️', k: 'index up' },
        { e: '👍', k: 'thumbs up' }, { e: '👎', k: 'thumbs down' }, { e: '✊', k: 'fist' },
        { e: '👊', k: 'punch' }, { e: '🤛', k: 'left fist' }, { e: '🤜', k: 'right fist' },
        { e: '👏', k: 'clap' }, { e: '🙌', k: 'raising hands' }, { e: '👐', k: 'open hands' },
        { e: '🤲', k: 'palms up' }, { e: '🤝', k: 'handshake' }, { e: '🙏', k: 'pray thanks' },
        { e: '💪', k: 'muscle' }, { e: '🦾', k: 'mechanical arm' }, { e: '🦵', k: 'leg' },
        { e: '🦶', k: 'foot' }, { e: '👂', k: 'ear' }, { e: '🦻', k: 'hearing aid' },
        { e: '👃', k: 'nose' }, { e: '🧠', k: 'brain' }, { e: '🫀', k: 'heart organ' },
        { e: '👀', k: 'eyes' }, { e: '👁️', k: 'eye' }, { e: '👅', k: 'tongue' },
        { e: '👄', k: 'mouth lips' }, { e: '👶', k: 'baby' }, { e: '🧒', k: 'child' },
        { e: '👦', k: 'boy' }, { e: '👧', k: 'girl' }, { e: '🧑', k: 'person' },
        { e: '👨', k: 'man' }, { e: '👩', k: 'woman' }, { e: '🧓', k: 'older person' },
        { e: '👴', k: 'old man' }, { e: '👵', k: 'old woman' }, { e: '🙍', k: 'frown person' },
        { e: '🙎', k: 'pouting' }, { e: '🙅', k: 'no gesture' }, { e: '🙆', k: 'ok gesture' },
        { e: '💁', k: 'information desk' }, { e: '🙋', k: 'raising hand person' },
        { e: '🙇', k: 'bow' }, { e: '🤦', k: 'facepalm' }, { e: '🤷', k: 'shrug' },
        { e: '🧑‍💼', k: 'office worker' }, { e: '👨‍💼', k: 'business man' }, { e: '👩‍💼', k: 'business woman' },
      ],
    },
    {
      id: 'nature',
      label: 'طبیعت',
      items: [
        { e: '🐶', k: 'dog' }, { e: '🐱', k: 'cat' }, { e: '🐭', k: 'mouse' },
        { e: '🐹', k: 'hamster' }, { e: '🐰', k: 'rabbit' }, { e: '🦊', k: 'fox' },
        { e: '🐻', k: 'bear' }, { e: '🐼', k: 'panda' }, { e: '🐨', k: 'koala' },
        { e: '🐯', k: 'tiger' }, { e: '🦁', k: 'lion' }, { e: '🐮', k: 'cow' },
        { e: '🐷', k: 'pig' }, { e: '🐸', k: 'frog' }, { e: '🐵', k: 'monkey' },
        { e: '🐔', k: 'chicken' }, { e: '🐧', k: 'penguin' }, { e: '🐦', k: 'bird' },
        { e: '🐤', k: 'chick' }, { e: '🦆', k: 'duck' }, { e: '🦅', k: 'eagle' },
        { e: '🦉', k: 'owl' }, { e: '🦇', k: 'bat' }, { e: '🐺', k: 'wolf' },
        { e: '🐴', k: 'horse' }, { e: '🦄', k: 'unicorn' }, { e: '🐝', k: 'bee' },
        { e: '🐛', k: 'bug' }, { e: '🦋', k: 'butterfly' }, { e: '🐌', k: 'snail' },
        { e: '🐢', k: 'turtle' }, { e: '🐍', k: 'snake' }, { e: '🦎', k: 'lizard' },
        { e: '🐙', k: 'octopus' }, { e: '🦑', k: 'squid' }, { e: '🦐', k: 'shrimp' },
        { e: '🐠', k: 'fish tropical' }, { e: '🐟', k: 'fish' }, { e: '🐬', k: 'dolphin' },
        { e: '🐳', k: 'whale' }, { e: '🌸', k: 'cherry blossom' }, { e: '🌹', k: 'rose' },
        { e: '🌺', k: 'hibiscus' }, { e: '🌻', k: 'sunflower' }, { e: '🌷', k: 'tulip' },
        { e: '🌱', k: 'seedling' }, { e: '🌲', k: 'evergreen' }, { e: '🌳', k: 'tree' },
        { e: '🌴', k: 'palm' }, { e: '🍀', k: 'clover' }, { e: '🍁', k: 'maple leaf' },
        { e: '🍂', k: 'fallen leaf' }, { e: '🍃', k: 'leaf wind' }, { e: '🌍', k: 'earth europe' },
        { e: '🌎', k: 'earth americas' }, { e: '🌏', k: 'earth asia' }, { e: '🌕', k: 'full moon' },
        { e: '🌙', k: 'crescent moon' }, { e: '⭐', k: 'star' }, { e: '🌟', k: 'glowing star' },
        { e: '✨', k: 'sparkles' }, { e: '⚡', k: 'lightning' }, { e: '🔥', k: 'fire' },
        { e: '💧', k: 'droplet' }, { e: '🌈', k: 'rainbow' }, { e: '☀️', k: 'sun' },
        { e: '🌤️', k: 'sun cloud' }, { e: '⛅', k: 'partly cloudy' }, { e: '🌧️', k: 'rain' },
        { e: '❄️', k: 'snowflake' }, { e: '☃️', k: 'snowman' },
      ],
    },
    {
      id: 'food',
      label: 'غذا',
      items: [
        { e: '🍎', k: 'apple red' }, { e: '🍐', k: 'pear' }, { e: '🍊', k: 'orange' },
        { e: '🍋', k: 'lemon' }, { e: '🍌', k: 'banana' }, { e: '🍉', k: 'watermelon' },
        { e: '🍇', k: 'grapes' }, { e: '🍓', k: 'strawberry' }, { e: '🫐', k: 'blueberries' },
        { e: '🍒', k: 'cherries' }, { e: '🥝', k: 'kiwi' }, { e: '🍅', k: 'tomato' },
        { e: '🥑', k: 'avocado' }, { e: '🥦', k: 'broccoli' }, { e: '🥕', k: 'carrot' },
        { e: '🌽', k: 'corn' }, { e: '🍞', k: 'bread' }, { e: '🥐', k: 'croissant' },
        { e: '🥖', k: 'baguette' }, { e: '🧀', k: 'cheese' }, { e: '🥚', k: 'egg' },
        { e: '🍳', k: 'cooking egg' }, { e: '🥞', k: 'pancakes' }, { e: '🧇', k: 'waffle' },
        { e: '🍔', k: 'burger' }, { e: '🍟', k: 'fries' }, { e: '🍕', k: 'pizza' },
        { e: '🌭', k: 'hotdog' }, { e: '🥪', k: 'sandwich' }, { e: '🌮', k: 'taco' },
        { e: '🌯', k: 'burrito' }, { e: '🥗', k: 'salad' }, { e: '🍝', k: 'spaghetti' },
        { e: '🍜', k: 'noodles ramen' }, { e: '🍲', k: 'pot food' }, { e: '🍛', k: 'curry' },
        { e: '🍣', k: 'sushi' }, { e: '🍱', k: 'bento' }, { e: '🍰', k: 'cake' },
        { e: '🎂', k: 'birthday cake' }, { e: '🧁', k: 'cupcake' }, { e: '🍩', k: 'donut' },
        { e: '🍪', k: 'cookie' }, { e: '🍫', k: 'chocolate' }, { e: '🍬', k: 'candy' },
        { e: '🍭', k: 'lollipop' }, { e: '☕', k: 'coffee' }, { e: '🍵', k: 'tea' },
        { e: '🧃', k: 'juice box' }, { e: '🥤', k: 'cup straw' }, { e: '🍺', k: 'beer' },
        { e: '🍷', k: 'wine' }, { e: '🥂', k: 'champagne' },
      ],
    },
    {
      id: 'activity',
      label: 'فعالیت',
      items: [
        { e: '⚽', k: 'soccer football' }, { e: '🏀', k: 'basketball' }, { e: '🏈', k: 'football' },
        { e: '⚾', k: 'baseball' }, { e: '🎾', k: 'tennis' }, { e: '🏐', k: 'volleyball' },
        { e: '🏓', k: 'ping pong' }, { e: '🏸', k: 'badminton' }, { e: '🥊', k: 'boxing' },
        { e: '🎯', k: 'target dart' }, { e: '🎳', k: 'bowling' }, { e: '🎮', k: 'video game' },
        { e: '🎲', k: 'dice' }, { e: '🧩', k: 'puzzle' }, { e: '🎭', k: 'performing arts' },
        { e: '🎨', k: 'art palette' }, { e: '🎬', k: 'clapper' }, { e: '🎤', k: 'microphone' },
        { e: '🎧', k: 'headphones' }, { e: '🎼', k: 'music score' }, { e: '🎹', k: 'piano' },
        { e: '🎸', k: 'guitar' }, { e: '🎺', k: 'trumpet' }, { e: '🎻', k: 'violin' },
        { e: '🏆', k: 'trophy' }, { e: '🏅', k: 'medal' }, { e: '🥇', k: 'gold medal' },
        { e: '🎖️', k: 'military medal' }, { e: '🏃', k: 'running' }, { e: '🚴', k: 'biking' },
        { e: '🏊', k: 'swimming' }, { e: '🧘', k: 'yoga' }, { e: '💃', k: 'dance woman' },
        { e: '🕺', k: 'dance man' }, { e: '🎉', k: 'party popper' }, { e: '🎊', k: 'confetti' },
        { e: '🎁', k: 'gift present' }, { e: '🎈', k: 'balloon' },
      ],
    },
    {
      id: 'travel',
      label: 'سفر',
      items: [
        { e: '🚗', k: 'car' }, { e: '🚕', k: 'taxi' }, { e: '🚙', k: 'suv' },
        { e: '🚌', k: 'bus' }, { e: '🚎', k: 'trolleybus' }, { e: '🏎️', k: 'race car' },
        { e: '🚓', k: 'police car' }, { e: '🚑', k: 'ambulance' }, { e: '🚒', k: 'fire engine' },
        { e: '🚐', k: 'minibus' }, { e: '🛻', k: 'pickup' }, { e: '🚚', k: 'truck' },
        { e: '🚲', k: 'bicycle' }, { e: '🛵', k: 'scooter' }, { e: '🏍️', k: 'motorcycle' },
        { e: '🚂', k: 'train' }, { e: '🚆', k: 'train front' }, { e: '🚇', k: 'metro' },
        { e: '✈️', k: 'airplane' }, { e: '🛫', k: 'departure' }, { e: '🛬', k: 'arrival' },
        { e: '🚀', k: 'rocket' }, { e: '🛸', k: 'ufo' }, { e: '🚁', k: 'helicopter' },
        { e: '⛵', k: 'sailboat' }, { e: '🚢', k: 'ship' }, { e: '⚓', k: 'anchor' },
        { e: '🏠', k: 'house home' }, { e: '🏡', k: 'house garden' }, { e: '🏢', k: 'office building' },
        { e: '🏬', k: 'department store' }, { e: '🏥', k: 'hospital' }, { e: '🏫', k: 'school' },
        { e: '🏛️', k: 'classical building' }, { e: '🕌', k: 'mosque' }, { e: '⛪', k: 'church' },
        { e: '🗼', k: 'tokyo tower' }, { e: '🗽', k: 'statue liberty' }, { e: '🗺️', k: 'map' },
        { e: '🧭', k: 'compass' }, { e: '🏖️', k: 'beach' }, { e: '🏔️', k: 'mountain snow' },
        { e: '⛰️', k: 'mountain' }, { e: '🌋', k: 'volcano' }, { e: '🏕️', k: 'camping' },
        { e: '🛎️', k: 'bellhop' }, { e: '🧳', k: 'luggage' },
      ],
    },
    {
      id: 'objects',
      label: 'اشیا',
      items: [
        { e: '⌚', k: 'watch' }, { e: '📱', k: 'phone mobile' }, { e: '💻', k: 'laptop' },
        { e: '⌨️', k: 'keyboard' }, { e: '🖥️', k: 'desktop' }, { e: '🖨️', k: 'printer' },
        { e: '📷', k: 'camera' }, { e: '📹', k: 'video camera' }, { e: '📞', k: 'telephone' },
        { e: '📺', k: 'tv' }, { e: '📻', k: 'radio' }, { e: '⏰', k: 'alarm clock' },
        { e: '🔋', k: 'battery' }, { e: '🔌', k: 'electric plug' }, { e: '💡', k: 'light bulb idea' },
        { e: '🔦', k: 'flashlight' }, { e: '🕯️', k: 'candle' }, { e: '🧯', k: 'fire extinguisher' },
        { e: '🔑', k: 'key' }, { e: '🗝️', k: 'old key' }, { e: '🔒', k: 'lock' },
        { e: '🔓', k: 'unlock' }, { e: '📎', k: 'paperclip' }, { e: '📌', k: 'pushpin' },
        { e: '📍', k: 'pin location' }, { e: '✂️', k: 'scissors' }, { e: '📝', k: 'memo note' },
        { e: '✏️', k: 'pencil' }, { e: '📚', k: 'books' }, { e: '📖', k: 'open book' },
        { e: '📰', k: 'newspaper' }, { e: '🗞️', k: 'rolled newspaper' }, { e: '💼', k: 'briefcase' },
        { e: '📁', k: 'folder' }, { e: '📂', k: 'open folder' }, { e: '🗂️', k: 'card index' },
        { e: '🛠️', k: 'hammer wrench tools' }, { e: '🔧', k: 'wrench' }, { e: '🔨', k: 'hammer' },
        { e: '⚙️', k: 'gear settings' }, { e: '💎', k: 'gem diamond' }, { e: '💍', k: 'ring' },
        { e: '👑', k: 'crown' }, { e: '👓', k: 'glasses' }, { e: '🕶️', k: 'sunglasses' },
        { e: '🎒', k: 'backpack' }, { e: '👜', k: 'handbag' }, { e: '👝', k: 'pouch' },
      ],
    },
    {
      id: 'symbols',
      label: 'نماد',
      items: [
        { e: '❤️', k: 'red heart love' }, { e: '🧡', k: 'orange heart' }, { e: '💛', k: 'yellow heart' },
        { e: '💚', k: 'green heart' }, { e: '💙', k: 'blue heart' }, { e: '💜', k: 'purple heart' },
        { e: '🖤', k: 'black heart' }, { e: '🤍', k: 'white heart' }, { e: '🤎', k: 'brown heart' },
        { e: '💔', k: 'broken heart' }, { e: '❣️', k: 'heart exclamation' }, { e: '💕', k: 'two hearts' },
        { e: '💞', k: 'revolving hearts' }, { e: '💓', k: 'beating heart' }, { e: '💗', k: 'growing heart' },
        { e: '💖', k: 'sparkling heart' }, { e: '💘', k: 'heart arrow cupid' }, { e: '💝', k: 'heart ribbon' },
        { e: '💯', k: 'hundred perfect' }, { e: '💢', k: 'anger' }, { e: '💥', k: 'collision boom' },
        { e: '💫', k: 'dizzy star' }, { e: '💦', k: 'sweat droplets' }, { e: '💤', k: 'zzz sleep' },
        { e: '✅', k: 'check mark button' }, { e: '❌', k: 'cross mark' }, { e: '❓', k: 'question' },
        { e: '❗', k: 'exclamation' }, { e: '‼️', k: 'double exclamation' }, { e: '⁉️', k: 'interrobang' },
        { e: '💬', k: 'speech balloon chat' }, { e: '💭', k: 'thought balloon' }, { e: '🔔', k: 'bell' },
        { e: '🔕', k: 'bell slash mute' }, { e: '🎵', k: 'music note' }, { e: '🎶', k: 'music notes' },
        { e: '♻️', k: 'recycle' }, { e: '⚠️', k: 'warning' }, { e: '🚫', k: 'prohibited' },
        { e: '🔞', k: 'underage' }, { e: '📛', k: 'name badge' }, { e: '🔰', k: 'beginner' },
        { e: '⭕', k: 'hollow red circle' }, { e: '✔️', k: 'check' }, { e: '➕', k: 'plus' },
        { e: '➖', k: 'minus' }, { e: '➗', k: 'divide' }, { e: '✖️', k: 'multiply' },
        { e: '♾️', k: 'infinity' }, { e: '💲', k: 'dollar' }, { e: '💱', k: 'currency exchange' },
      ],
    },
    {
      id: 'flags',
      label: 'پرچم',
      items: [
        { e: '🇮🇷', k: 'iran flag' }, { e: '🇺🇸', k: 'usa flag' }, { e: '🇬🇧', k: 'uk flag' },
        { e: '🇩🇪', k: 'germany flag' }, { e: '🇫🇷', k: 'france flag' }, { e: '🇮🇹', k: 'italy flag' },
        { e: '🇪🇸', k: 'spain flag' }, { e: '🇷🇺', k: 'russia flag' }, { e: '🇨🇳', k: 'china flag' },
        { e: '🇯🇵', k: 'japan flag' }, { e: '🇰🇷', k: 'korea flag' }, { e: '🇮🇳', k: 'india flag' },
        { e: '🇹🇷', k: 'turkey flag' }, { e: '🇸🇦', k: 'saudi flag' }, { e: '🇦🇪', k: 'uae flag' },
        { e: '🇶🇦', k: 'qatar flag' }, { e: '🇮🇶', k: 'iraq flag' }, { e: '🇦🇫', k: 'afghanistan flag' },
        { e: '🇵🇰', k: 'pakistan flag' }, { e: '🇦🇿', k: 'azerbaijan flag' }, { e: '🇦🇲', k: 'armenia flag' },
        { e: '🇨🇦', k: 'canada flag' }, { e: '🇧🇷', k: 'brazil flag' }, { e: '🇦🇺', k: 'australia flag' },
        { e: '🏁', k: 'checkered flag' }, { e: '🚩', k: 'triangular flag' }, { e: '🎌', k: 'crossed flags' },
      ],
    },
  ];

  var ALL_ITEMS = [];
  CATEGORIES.forEach(function (cat) {
    if (cat.id === 'recent') return;
    cat.items.forEach(function (it) { ALL_ITEMS.push(it); });
  });

  function loadRecent() {
    try {
      var raw = localStorage.getItem(RECENT_KEY);
      if (!raw) return [];
      return JSON.parse(raw).filter(function (e) { return typeof e === 'string' && e.length; }).slice(0, RECENT_MAX);
    } catch (e) {
      return [];
    }
  }

  function pushRecent(emoji) {
    var list = loadRecent().filter(function (e) { return e !== emoji; });
    list.unshift(emoji);
    if (list.length > RECENT_MAX) list = list.slice(0, RECENT_MAX);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch (e) {}
    var recentCat = CATEGORIES[0];
    recentCat.items = list.map(function (e) { return { e: e, k: '' }; });
  }

  function isMobile() {
    return window.matchMedia('(max-width: 768px)').matches;
  }

  function insertAtCursor(textarea, text) {
    if (!textarea || !text) return;
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var val = textarea.value || '';
    var max = textarea.maxLength > 0 ? textarea.maxLength : Infinity;
    var nextLen = val.length - (end - start) + text.length;
    if (nextLen > max) {
      var room = max - (val.length - (end - start));
      if (room <= 0) return;
      text = text.slice(0, room);
    }
    textarea.value = val.slice(0, start) + text + val.slice(end);
    var pos = start + text.length;
    textarea.setSelectionRange(pos, pos);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.focus();
  }

  function EmojiPicker(opts) {
    this.toggle = opts.toggle;
    this.popover = opts.popover;
    this.textarea = opts.textarea;
    this.onPick = opts.onPick || function () {};
    this.activeCat = 'smileys';
    this.open = false;
    this._bind();
    CATEGORIES[0].items = loadRecent().map(function (e) { return { e: e, k: '' }; });
  }

  EmojiPicker.prototype._bind = function () {
    var self = this;
    this._renderShell();
    this.toggle.addEventListener('click', function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      if (self.open) self.close();
      else self.openPicker();
    });
    document.addEventListener('click', function (ev) {
      if (!self.open) return;
      if (ev.target.closest('#' + self.popover.id) || ev.target.closest('#' + self.toggle.id)) return;
      self.close();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && self.open) {
        ev.preventDefault();
        self.close();
      }
    });
    this.popover.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        self.close();
        self.toggle.focus();
      }
    });
  };

  EmojiPicker.prototype._renderShell = function () {
    this.popover.innerHTML =
      '<div class="cf-emoji-popover__head">' +
      '<input type="search" class="cf-emoji-popover__search" placeholder="جستجو…" autocomplete="off" aria-label="جستجوی ایموجی">' +
      '<button type="button" class="cf-icon-btn cf-icon-btn--sm cf-emoji-popover__close" aria-label="بستن"><i class="fas fa-times" aria-hidden="true"></i></button>' +
      '</div>' +
      '<div class="cf-emoji-popover__tabs" role="tablist"></div>' +
      '<div class="cf-emoji-popover__grid" role="listbox" tabindex="0"></div>';
    this.searchInput = this.popover.querySelector('.cf-emoji-popover__search');
    this.tabsEl = this.popover.querySelector('.cf-emoji-popover__tabs');
    this.gridEl = this.popover.querySelector('.cf-emoji-popover__grid');
    var self = this;
    this.searchInput.addEventListener('input', function () { self._renderGrid(); });
    this.popover.querySelector('.cf-emoji-popover__close').addEventListener('click', function () {
      self.close();
    });
    CATEGORIES.forEach(function (cat) {
      if (cat.id === 'recent' && !cat.items.length) return;
      var tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'cf-emoji-popover__tab';
      tab.textContent = cat.label;
      tab.dataset.cat = cat.id;
      tab.setAttribute('role', 'tab');
      tab.addEventListener('click', function () {
        self.activeCat = cat.id;
        self.searchInput.value = '';
        self._syncTabs();
        self._renderGrid();
      });
      self.tabsEl.appendChild(tab);
    });
    this._syncTabs();
    this._renderGrid();
  };

  EmojiPicker.prototype._syncTabs = function () {
    var self = this;
    this.tabsEl.querySelectorAll('.cf-emoji-popover__tab').forEach(function (t) {
      var on = t.dataset.cat === self.activeCat;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  };

  EmojiPicker.prototype._itemsForView = function () {
    var q = (this.searchInput.value || '').trim().toLowerCase();
    if (q) {
      return ALL_ITEMS.filter(function (it) {
        return it.k.indexOf(q) >= 0 || it.e.indexOf(q) >= 0;
      });
    }
    var active = this.activeCat;
    var cat = CATEGORIES.find(function (c) { return c.id === active; });
    if (!cat || (cat.id === 'recent' && !cat.items.length)) {
      cat = CATEGORIES.find(function (c) { return c.id === 'smileys'; });
    }
    return cat ? cat.items : [];
  };

  EmojiPicker.prototype._renderGrid = function () {
    var self = this;
    var items = this._itemsForView();
    this.gridEl.innerHTML = '';
    if (!items.length) {
      var empty = document.createElement('p');
      empty.className = 'cf-emoji-popover__empty';
      empty.textContent = 'ایموجی پیدا نشد';
      this.gridEl.appendChild(empty);
      return;
    }
    items.forEach(function (it) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cf-emoji-popover__cell';
      btn.textContent = it.e;
      btn.setAttribute('role', 'option');
      btn.setAttribute('aria-label', it.k || 'emoji');
      btn.addEventListener('click', function () {
        self._pick(it.e);
      });
      self.gridEl.appendChild(btn);
    });
  };

  EmojiPicker.prototype._pick = function (emoji) {
    pushRecent(emoji);
    CATEGORIES[0].items = loadRecent().map(function (e) { return { e: e, k: '' }; });
    insertAtCursor(this.textarea, emoji);
    this.onPick(emoji);
    if (isMobile()) this.close();
  };

  EmojiPicker.prototype.openPicker = function () {
    this.open = true;
    this.popover.hidden = false;
    this.toggle.setAttribute('aria-expanded', 'true');
    this.popover.classList.toggle('cf-emoji-popover--sheet', isMobile());
    if (isMobile()) {
      document.body.classList.add('cf-emoji-sheet-open');
    }
    this._renderGrid();
    this.searchInput.value = '';
    this.searchInput.focus();
  };

  EmojiPicker.prototype.close = function () {
    this.open = false;
    this.popover.hidden = true;
    this.toggle.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('cf-emoji-sheet-open');
  };

  global.CFForumEmoji = {
    insertAtCursor: insertAtCursor,
    createPicker: function (opts) {
      return new EmojiPicker(opts);
    },
    REACTION_EMOJIS: ['👍', '❤️', '👏', '😂', '🙏'],
  };
})(window);
