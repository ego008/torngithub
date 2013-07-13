import tornado.ioloop
import tornado.web
import tornado.escape
import tornado.options
import tornado.httputil
import logging

from tornado.options import define, options

import torngithub

log = logging.getLogger("github.demo")

define("port", default=8088, help="run on the given port", type=int)
define("github_client_id", help="your Github application Client ID",
       default="ae63fe642fd528d90bdd")
define("github_client_secret", help="your Github application Client Secret",
       default="1c3acadf6179db7e9fba6d2c6f052f898c00d88b")
define("github_callback_path", help="your Github application Callback",
       default="/auth")
define("github_scope", help="github scope", default="")

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            return None
        return tornado.escape.json_decode(user_json)

class MainHandler(BaseHandler, torngithub.GithubMixin):
    def get(self):
        if self.current_user:
            self.write('Login User: ' + self.current_user["name"]
                       + ' <a href="/stars">My Stars</a> '
                       + ' <a href="/logout">Logout</a>')
        else:
            self.write('<a href="'
                       + self.settings["github_callback_path"] + '">Login</a>')
        

class GithubLoginHandler(tornado.web.RequestHandler, torngithub.GithubMixin):
    @tornado.web.asynchronous
    def get(self):
        # we can append next to the redirect uri, so the user gets the
        # correct URL on login
        redirect_uri = tornado.httputil.url_concat(self.request.protocol
                                                   + "://" + self.request.host
                                                   + self.settings["github_callback_path"],
                                                   {"next": self.get_argument('next', '/')})

        # if we have a code, we have been authorized so we can log in
        if self.get_argument("code", False):
            self.get_authenticated_user(
                redirect_uri=redirect_uri,
                client_id=self.settings["github_client_id"],
                client_secret=self.settings["github_client_secret"],
                code=self.get_argument("code"),
                callback=self.async_callback(self._on_login))
            return

        # otherwise we need to request an authorization code
        self.authorize_redirect(
            redirect_uri=redirect_uri,
            client_id=self.settings["github_client_id"],
            extra_params={"scope": self.settings['github_scope'], "foo":1})

    def _on_login(self, user):
        """ This handles the user object from the login request """
        if user:
            log.info('logged in user from github: ' + str(user))
            self.set_secure_cookie("user", tornado.escape.json_encode(user))
        else:
            self.clear_cookie("user")
        self.redirect(self.get_argument("next","/"))


class StarsHandler(BaseHandler, torngithub.GithubMixin):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        self.github_request(
            '/user/starred', self._on_get_stars,
            access_token=self.current_user['access_token'])

    def _on_get_stars(self, stars):
        self.write(tornado.escape.json_encode(stars))
        self.finish()

class LogoutHandler(BaseHandler, torngithub.GithubMixin):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))

def main():
    tornado.options.parse_command_line()
    handlers = [
        (r"/", MainHandler),
        (r"/stars", StarsHandler),
        (options.github_callback_path, GithubLoginHandler),
        (r"/logout", LogoutHandler)
    ]

    settings = dict(
        cookie_secret="asdf",
        login_url=options.github_callback_path,
        xsrf_cookies=True,
        github_client_id=options.github_client_id,
        github_client_secret=options.github_client_secret,
        github_callback_path=options.github_callback_path,
        github_scope=options.github_scope,
        debug=True,
        autoescape=None
    )

    application = tornado.web.Application(handlers, **settings)
    application.listen(options.port)
    tornado.ioloop.IOLoop().instance().start()

if __name__ == "__main__":
    main()