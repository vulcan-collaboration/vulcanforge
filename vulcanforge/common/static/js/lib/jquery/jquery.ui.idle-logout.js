// jQuery idleLogout plugin v-0.1
// ==============================
// 
// Idle logout maintianing one session across multiple tabs/windows.
//
// http://github.com/rennat/jquery-idle-logout

(function ($) {
  var IDLE;
  // =================
  // idleLogout object
  // =================
  IDLE = {
    // ----------------
    // default settings
    // ----------------
    // any of these can be overridden in initialization
    settings: {
      // seconds of idle time before logout (includes countdown time)
      logoutSeconds: 20 * 60,
      // countdown length in seconds
      countdownSeconds: 30,
      // message used in countdown popup
      // "{countdown}" will be replaced with, you guessed it, a countdown timer
      countdownMessage: "You will be logged out due to inactivity in {countdown} seconds.",
      // redirect to this url after timeout
      logoutUrl: '/logout',
      // $.cookie options
      cookieOptions: {
        path: '/'
      },
      // update time in milliseconds
      updateMilliseconds: 300,
      // listen to these events
      bindEvents: "mousemove mousedown mouseup keydown keyup focus blur"
    },
    // ------------------
    // private properties
    // ------------------
    idleTime: null,
    logoutTime: null,
    idleTimeout: null,
    logoutTimeout: null,
    countdownInterval: null,
    countingDown: false,
    $countdownDialog: null,
    $countdownText: null,
    // --------------
    // event handlers
    // --------------
    handlers: {
      // user has taken some action
      "UserActivity": function (e) {
        if (!IDLE.countingDown) {
          // reset the timers
          IDLE._reset();
        }
      },
      // user has gone idle in this context
      "UserIdle": function (e) {
        // check the cookie in case it's been updated elsewhere
        if (IDLE._inSyncWithCookie()) {
          // start the logout countdown
          IDLE._startCountdown();
        } else {
          // reset from the cookie's time
          IDLE._reset(IDLE._getCookie());
        }
      },
      // log the user out
      "IdleLogout": function (e) {
        var d = new Date();
        d.setTime(d.getTime() + 10*1000);
        $.cookie('idleLogout.loggedOut', 'true', {
          path: '/',
          expires: d
        });
        window.location.href = IDLE.settings.logoutUrl;
      },
      "CancelLogout": function (e) {
        IDLE._stopCountdown();
        // trigger activity
        IDLE._reset();
      },
      // update the countdown and check for cancellation in other tabs
      "IdleDialogUpdate": function (e) {
        // check the cookie
        if (IDLE._inSyncWithCookie()) {
          // update counter
          IDLE._updateCountdown();
        } else {
          // stop the countdown
          IDLE._stopCountdown();
          // reset from the cookie's time
          IDLE._reset(IDLE._getCookie());
        }
      }
    },
    // --------------
    // public methods
    // --------------
    // start the idle timers
    init: function (options) {
      // initialize settings
      IDLE.settings = $.extend(IDLE.settings, options);
      // bind activity events
      $(document).bind(IDLE.settings.bindEvents, function (e) {
        $(document).trigger('UserActivity.idleLogout', e);
      });
      // bind event handlers
      $.each(IDLE.handlers, function (eventName, handler) {
        $(document).bind(eventName+'.idleLogout', handler);
      });
      // prepare dialog
      IDLE._initDialog();
      // reset time to now
      IDLE._reset();
    },
    // ---------------
    // private methods
    // ---------------
    // update the timer from the given time (default to now)
    _reset: function (opt_time) {
      var
        now = new Date().getTime(),
        // calculate the time the user will be logged out
        logoutTime = IDLE.logoutTime = !!opt_time ? opt_time : now + IDLE.settings.logoutSeconds * 1000,
        // calculate logout delay
        logoutDelay = logoutTime - now,
        // calculate idle delay
        idleDelay = logoutDelay - IDLE.settings.countdownSeconds * 1000;
      // clear the existing logout timeout
      if (IDLE.logoutTimeout) {window.clearTimeout(IDLE.logoutTimeout);}
      // clear the existing idle timeout
      if (IDLE.idleTimeout) {window.clearTimeout(IDLE.idleTimeout);}
      // set the logout timeout
      IDLE.logoutTimeout = window.setTimeout(function () {
        $(document).trigger('IdleLogout.idleLogout');
      }, logoutDelay);
      // set the idle timeout
      IDLE.idleTimeout = window.setTimeout(function () {
        $(document).trigger('UserIdle.idleLogout');
      }, idleDelay);
      if (typeof opt_time === 'undefined') {
        // update the cookie
        IDLE._setCookie(logoutTime);
      }
    },
    // consistently set the cookie
    _setCookie: function (value) {
      $.cookie('idleLogout.logoutTime', value, IDLE.settings.cookieOptions);
    },
    // consistently get the cookie
    _getCookie: function () {
      return window.parseInt($.cookie('idleLogout.logoutTime'));
    },
    // does the current state match the cookie?
    _inSyncWithCookie: function () {
      var cookieValue = IDLE._getCookie();
      return IDLE.logoutTime === cookieValue;
    },
    // create but dont open the countdown dialog
    _initDialog: function () {
      var
        // prepare the message template
        message = IDLE.settings.countdownMessage.replace('{countdown}', '<span class="countdown-timer"></span>');
      // save the jQuery selection
      IDLE.$countdownDialog = $('<div>' + message + '</div>');
      // save the countdown timer selection
      IDLE.$countdownText = IDLE.$countdownDialog.find('.countdown-timer');
      // create the jQuery UI dialog
      IDLE.$countdownDialog.dialog({
        resizable: false,
        autoOpen: false,
        modal: true,
        buttons: {
          "Cancel Logout": function () {
            IDLE.$countdownDialog.dialog('close');
          }
        },
        close: function () {
          $(document).trigger('CancelLogout.idleLogout');
        }
      });
    },
    // begin the countdown and start update interval
    _startCountdown: function () {
      IDLE.countingDown = true;
      IDLE.$countdownDialog.dialog('open');
      IDLE.countdownInterval = window.setInterval(function () {
        $(document).trigger('IdleDialogUpdate.idleLogout');
      }, IDLE.settings.updateMilliseconds);
    },
    _stopCountdown: function () {
      if (IDLE.countdownInterval) {
        window.clearInterval(IDLE.countdownInterval);
      }
      if (IDLE.$countdownDialog.dialog('_isOpen')) {
        IDLE.$countdownDialog.dialog('close');
      }
      IDLE.countingDown = false;
    },
    _updateCountdown: function () {
      var seconds = Math.ceil((IDLE.logoutTime - new Date().getTime())/1000);
      IDLE.$countdownText.text(seconds);
    }
  };
  // --------------------------
  // jQuery plugin registration
  // --------------------------
  $.idleLogout = function (method) {
    if (IDLE[method] && method.substr(0,1) !== '_') {
      return IDLE[method].apply(this, Array.prototype.slice.call(arguments, 1));
    } else if (typeof method === 'object' || !method) {
      return IDLE.init.apply(this, arguments);
    } else {
      $.error('Method ' +  method + ' does not exist on jQuery.idleLogout');
    }
  };
}(jQuery));
